"""Demo/Office web wrapper: one FastAPI process serves mockup/ and a small JSON API over the frozen core
(cli.answer -> verify_lines). Run: uvicorn desk.web:app --port 8080  (or python -m desk web)."""
import datetime as dt
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import audit, cases, llm
from .applicability import assess, letter_tokens
from .audit import IST, data_dir

ROOT = Path(__file__).resolve().parent.parent
COOKIE = "desk_demo"
CLOUD = {"groq", "cerebras"}
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
MAX_CALLS, MAX_TOKENS = 3, 20000  # Demo caps per case
BLOCKING = {"FLAG", "FLAG no_source", "FLAG unknown_source", "FLAG wrong_source", "FLAG not_in_retrieved"}
MAX_UPLOAD = 5 * 1024 * 1024
STATE = {"embedder": None, "ready": threading.Event(), "warm_error": None}
JOB_LOCK = threading.Lock()  # one drafting job at a time (RAM)


def mode():
    return os.environ.get("DESK_MODE", "demo").strip().lower()


def check_mode(env=None, provider=None, base=None):
    """Office mode refuses any cloud LLM or non-local base URL. Raises RuntimeError (process exits non-zero)."""
    env = os.environ if env is None else env
    m = env.get("DESK_MODE", "demo").strip().lower()
    if m not in ("demo", "office"):
        raise RuntimeError("DESK_MODE must be demo or office")
    if m == "office":
        provider = provider or llm.PROVIDER
        if provider in CLOUD or env.get("DESK_LLM_PROVIDER", "").lower() in CLOUD:
            raise RuntimeError(f"office mode refuses cloud LLM provider {provider!r}")
        for url in [env.get(k) for k in ("OPENAI_BASE_URL", "GROQ_BASE_URL", "CEREBRAS_BASE_URL", "LMSTUDIO_URL")] + [base or llm.BASE]:
            if url and urlparse(url).hostname not in LOCAL_HOSTS:
                raise RuntimeError("office mode: LLM base URL must be localhost")
    return m


def db_path():
    return data_dir() / "index.db"


def open_db():
    from .store import connect
    return connect(db_path())


def answer_fn(*a, **kw):
    from .cli import answer
    return answer(*a, **kw)


def load_archive_fn(con, files):
    from .cli import load_archive
    return load_archive(con, files)


def doc_shas_fn(con, files):
    out = {}
    for f in files:
        row = con.execute("SELECT sha256 FROM docs WHERE file=?", (f,)).fetchone()
        out[f] = row[0] if row else None
    return out


def verify_fn(lines, archive):
    from .verify import verify_lines
    return verify_lines(lines, archive)


def extract_text(path):
    from .extract import extract_pages
    return "\n".join(t for _, t in extract_pages(path))


def warm():
    """Embedder + reranker loaded once per process (background thread so the port opens at once)."""
    try:
        if STATE["embedder"] is None:
            from .embed import Embedder
            STATE["embedder"] = Embedder()
        if os.environ.get("DESK_NO_RERANK") != "1":
            from . import rerank
            rerank.warm_up()
    except Exception as e:  # reported by /api/health
        STATE["warm_error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        STATE["ready"].set()


def seed_index():
    seed = os.environ.get("DESK_SEED_DB")
    if seed and Path(seed).exists() and not db_path().exists():
        db_path().parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, db_path())


def recover_jobs():
    for m in cases.list_cases():
        if m["status"] in ("queued", "running"):
            cases.set_status(m["case_id"], "error", error="interrupted_by_restart")


@asynccontextmanager
async def lifespan(app):
    if check_mode() == "office":
        os.environ["HF_HUB_OFFLINE"] = "1"  # models must already be in DESK_CACHE; no hub calls from the office PC
    data_dir().mkdir(parents=True, exist_ok=True)
    seed_index()
    recover_jobs()
    if os.environ.get("DESK_WEB_WARM", "1") == "1":
        threading.Thread(target=warm, daemon=True).start()
    else:
        STATE["ready"].set()
    yield


app = FastAPI(title="Office Desk Agent", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def _token():
    p = os.environ.get("DESK_DEMO_PASSCODE", "")
    return hashlib.sha256(f"desk-demo:{p}".encode()).hexdigest() if p else None


@app.middleware("http")
async def gate(request: Request, call_next):
    path = request.url.path
    if mode() == "demo" and path.startswith("/api/") and path not in ("/api/login", "/api/health"):
        tok = _token()
        if not tok or not hmac.compare_digest(request.cookies.get(COOKIE, ""), tok):
            return JSONResponse({"error": "login required"}, status_code=401)
    return await call_next(request)


def err(code, msg, **extra):
    return JSONResponse({"error": msg, **extra}, status_code=code)


def _case_or_404(case_id):
    try:
        return cases.get_case(case_id)
    except cases.CaseNotFound:
        return None


@app.get("/api/health")
def health():
    m = mode()
    return {"mode": m, "demo_banner": m == "demo", "login_required": m == "demo", "model_id": llm.DEFAULT_MODEL,
            "provider": llm.PROVIDER, "engine_ready": STATE["ready"].is_set() and not STATE["warm_error"],
            "engine_error": STATE["warm_error"], "index": db_path().exists()}


@app.post("/api/login")
async def login(request: Request):
    if mode() != "demo":
        return Response(status_code=204)
    tok = _token()
    if not tok:
        return err(503, "DESK_DEMO_PASSCODE is not set on the server")
    try:
        body = await request.json()
    except Exception:
        body = {}
    p = str((body or {}).get("passcode", ""))
    if not hmac.compare_digest(hashlib.sha256(f"desk-demo:{p}".encode()).hexdigest(), tok):
        return err(401, "wrong passcode")
    r = Response(status_code=204)
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    r.set_cookie(COOKIE, tok, httponly=True, secure=secure, samesite="strict", max_age=7 * 24 * 3600)
    return r


@app.get("/api/cases")
def list_cases():
    return [{k: m.get(k) for k in ("case_id", "sha256", "status", "created_ts", "lang", "filename", "no_matching_record")}
            for m in cases.list_cases()]


@app.post("/api/cases")
async def create(file: UploadFile = File(...), lang: str = Form("en"), ref_no: str = Form(""), office: str = Form(""),
                 to: str = Form(""), signatory: str = Form(""), subject: str = Form("")):
    name = Path(file.filename or "letter.txt").name
    if Path(name).suffix.lower() not in (".txt", ".pdf"):
        return err(415, "only .txt or .pdf letters")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        return err(413, "letter too large (5 MB max)")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / name
        tmp.write_bytes(data)
        cid = cases.create_case(tmp, lang=lang, mode=mode(), filename=name,
                                fields={"ref_no": ref_no, "office": office, "to": to, "signatory": signatory, "subject": subject})
    meta = cases.get_case(cid)
    try:
        cases.write_letter_text(cid, extract_text(cases.inbound_path(cid)))
    except Exception as e:
        cases.set_status(cid, "error", error=f"could not read letter: {type(e).__name__}")
    audit.append_event(cid, "intake", {"sha256": meta["sha256"], "filename": name, "lang": meta["lang"], "mode": meta["mode"],
                                       "bytes": len(data)})
    return {"case_id": cid, "status": cases.get_case(cid)["status"]}


class CapError(Exception):
    pass


def _capped_chat(cid, m):
    """chat_json with the Demo caps; never calls the LLM when retrieval found nothing."""
    calls = {"n": m.get("llm_calls", 0), "tokens": m.get("llm_tokens", 0)}
    demo = mode() == "demo"

    def chat(messages, schema, **kw):
        if "source_file:" not in messages[-1]["content"]:
            raise llm.LLMError("no_matching_record")
        est = sum(len(x["content"]) for x in messages) // 4
        if demo and (calls["n"] >= MAX_CALLS or calls["tokens"] + est > MAX_TOKENS):
            raise CapError
        calls["n"] += 1
        cases.update_meta(cid, llm_calls=calls["n"])
        data, stats = llm.chat_json(messages, schema, **kw)
        calls["tokens"] += (stats.get("prompt_tokens") or est) + (stats.get("completion_tokens") or len(json.dumps(data)) // 4)
        cases.update_meta(cid, llm_tokens=calls["tokens"])
        if demo and calls["tokens"] > MAX_TOKENS:
            raise CapError
        return data, stats
    return chat


def _heading_for(ln, lists):
    hits = [h for t in ("rules", "cases") for h in lists.get(t, [])]
    same = [h for h in hits if h["file"] == ln.get("source_file")]
    exact = [h for h in same if h["page"] == ln.get("page")]
    for h in exact + same:
        if h.get("heading"):
            return h["heading"]
    return None


def annotate(cid, lines, meta=None, ans=None, archive=None):
    """Fresh verify (+ not_in_retrieved), applicability and soft anchor for every cited line."""
    meta = meta or cases.get_case(cid)
    ans = ans if ans is not None else (cases.read_answer(cid) or {})
    archive = archive if archive is not None else cases.read_archive(cid)
    retrieved = set(meta.get("retrieved_files") or [])
    shas = meta.get("doc_sha256") or {}
    toks = letter_tokens(cases.read_letter_text(cid))
    lists = {t: ans.get(t) or [] for t in ("cases", "rules")}
    out = []
    for ln in lines:
        ln = {"sentence": str(ln.get("sentence") or "").strip(), "source_file": ln.get("source_file"), "page": ln.get("page"),
              "verbatim_quote": ln.get("verbatim_quote"), "line_type": ln.get("line_type") or "cited",
              "clerk_note": (ln.get("clerk_note") or None)}
        if ln["line_type"] == "cited":
            r = verify_fn([{k: ln[k] for k in ("sentence", "source_file", "page", "verbatim_quote")}], archive)[0]
            if ln["source_file"] and ln["source_file"] not in retrieved:
                r["status"], r["verified"] = "FLAG not_in_retrieved", False
            ln["verify"] = {k: r.get(k) for k in ("status", "verified", "found_page", "found_in", "page_note")}
            ln["applicability"] = assess(toks, _heading_for(ln, lists))
            ln["doc_sha256"] = shas.get(ln["source_file"])
        else:
            ln["verify"], ln["applicability"], ln["doc_sha256"] = None, None, None
        out.append(ln)
    return out


def failing(lines):
    bad = []
    for i, ln in enumerate(lines):
        if ln["line_type"] == "cited":
            v = ln.get("verify") or {}
            if v.get("status") in BLOCKING or str(v.get("status", "")).startswith("FLAG") or not v.get("verified"):
                bad.append({"index": i, "sentence": ln["sentence"], "status": v.get("status"), "source_file": ln.get("source_file"),
                            "page": ln.get("page")})
        elif ln["line_type"] == "clerk_fact" and not (ln.get("clerk_note") or "").strip():
            bad.append({"index": i, "sentence": ln["sentence"], "status": "clerk_note_missing"})
    return bad


def run_answer(cid):
    with JOB_LOCK:
        STATE["ready"].wait()
        meta = cases.set_status(cid, "running", error=None)
        con = None
        try:
            if STATE["warm_error"]:
                raise RuntimeError(f"engine not ready: {STATE['warm_error']}")
            con = open_db()  # own connection on this worker thread
            fields = {k: v for k, v in meta["fields"].items() if v and v != "____"}
            out = answer_fn(con, STATE["embedder"], cases.inbound_path(cid), lang=meta["lang"], fields=fields,
                            chat=_capped_chat(cid, meta))
            files = sorted({h["file"] for t in ("cases", "rules") for h in out.get(t) or []})
            nmr = not out.get("cases") and not out.get("rules")
            if nmr:
                out.pop("draft_error", None)
            archive = load_archive_fn(con, files)
            cases.write_archive(cid, archive)
            cases.write_answer(cid, out)
            meta = cases.update_meta(cid, retrieved_files=files, doc_sha256=doc_shas_fn(con, files), no_matching_record=nmr)
            d = out.get("draft") or {}
            lines = annotate(cid, [{**ln, "line_type": "cited"} for ln in d.get("lines", [])], meta, out,
                             cases.read_archive(cid)) if d else []
            v = cases.save_draft_version(cid, lines)
            derr = out.get("draft_error")
            cases.set_status(cid, "error" if derr else "done", error=derr)
            stats = d.get("llm_stats") or {}
            audit.append_event(cid, "answer_done", {"ok": not derr, "error": derr, "no_matching_record": nmr, "draft_version": v,
                                                     "lines": len(lines), "verified_pct": d.get("verified_pct"),
                                                     "retrieved_files": files, "mode": mode(), "provider": llm.PROVIDER,
                                                     "model": stats.get("model") or llm.DEFAULT_MODEL, "llm_endpoint": llm.BASE,
                                                     "retrieval_s": out.get("retrieval_s"), "total_s": out.get("total_s")})
        except CapError:
            cases.set_status(cid, "error", error="token_or_call_cap")
            audit.append_event(cid, "answer_done", {"ok": False, "error": "token_or_call_cap"})
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"[:300]
            cases.set_status(cid, "error", error=msg)
            audit.append_event(cid, "answer_done", {"ok": False, "error": msg})
        finally:
            if con is not None:
                con.close()


@app.post("/api/cases/{case_id}/answer")
def start_answer(case_id: str, bg: BackgroundTasks):
    m = _case_or_404(case_id)
    if not m:
        return err(404, "no such case")
    if m["status"] in ("running", "approved"):
        return err(409, f"case is {m['status']}")
    if mode() == "demo" and m.get("llm_calls", 0) >= MAX_CALLS:
        cases.set_status(case_id, "error", error="token_or_call_cap")
        return err(409, "token_or_call_cap")
    cases.set_status(case_id, "queued", error=None)
    audit.append_event(case_id, "answer_started", {"mode": mode(), "provider": llm.PROVIDER, "model": llm.DEFAULT_MODEL})
    bg.add_task(run_answer, case_id)
    return {"case_id": case_id, "status": "queued"}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    m = _case_or_404(case_id)
    if not m:
        return err(404, "no such case")
    ans = cases.read_answer(case_id) or {}
    d = cases.latest_draft(case_id)
    keep = ("rank", "file", "page", "heading", "score", "snippet")
    return {"case_id": case_id, "status": m["status"], "error": m.get("error"), "no_matching_record": m.get("no_matching_record"),
            "filename": m.get("filename"), "created_ts": m.get("created_ts"), "sha256": m.get("sha256"), "mode": m.get("mode"),
            "letter_text": cases.read_letter_text(case_id)[:6000],
            "summary": (ans.get("draft") or {}).get("summary"), "subject": (ans.get("draft") or {}).get("subject"),
            "sources": {t: [{k: h.get(k) for k in keep} for h in ans.get(t) or []] for t in ("cases", "rules")} if ans else None,
            "draft": d, "fields": {"lang": m["lang"], **m["fields"]},
            "outbox": cases.outbox_path(case_id).exists(), "approved_version": m.get("approved_version")}


@app.patch("/api/cases/{case_id}/draft")
async def patch_draft(case_id: str, request: Request):
    m = _case_or_404(case_id)
    if not m:
        return err(404, "no such case")
    if m["status"] != "done":
        return err(409, f"case is {m['status']}")
    body = await request.json()
    lines = body.get("lines") if isinstance(body, dict) else None
    if not isinstance(lines, list) or len(lines) > 40:
        return err(422, "body must be {lines: [...]}")
    for ln in lines:
        if not isinstance(ln, dict) or ln.get("line_type") not in cases.LINE_TYPES:
            return err(422, f"line_type must be one of {list(cases.LINE_TYPES)}")
        if not str(ln.get("sentence") or "").strip():
            return err(422, "every line needs a sentence")
        if ln["line_type"] == "clerk_fact" and not str(ln.get("clerk_note") or "").strip():
            return err(422, "clerk_fact lines need a clerk_note (the clerk's reason)")
    new = annotate(case_id, lines, m)
    v = cases.save_draft_version(case_id, new)
    audit.append_event(case_id, "draft_edited", {"draft_version": v, "lines": len(new),
                                                 "line_types": [ln["line_type"] for ln in new]})
    return {"version": v, "lines": new}


@app.post("/api/cases/{case_id}/approve")
async def approve(case_id: str, request: Request):
    m = _case_or_404(case_id)
    if not m:
        return err(404, "no such case")
    if m["status"] != "done":
        return err(409, f"case is {m['status']}", failing_lines=[])
    try:
        body = await request.json()
    except Exception:
        body = {}
    reason = str((body or {}).get("override_reason") or "").strip()
    d = cases.latest_draft(case_id)
    if not d or not d["lines"]:
        return err(409, "no draft lines: add clerk_fact or standard lines first", failing_lines=[])
    lines = annotate(case_id, d["lines"], m)  # re-run the quote check on this version
    bad = failing(lines)
    audit.append_event(case_id, "verify", {"draft_version": d["version"], "cited": sum(l["line_type"] == "cited" for l in lines),
                                           "failing": len(bad), "statuses": [(l.get("verify") or {}).get("status") for l in lines]})
    if bad and not reason:
        return err(409, "approve blocked: fix, mark as clerk fact, or give an override reason", failing_lines=bad)
    if bad:
        audit.append_event(case_id, "override", {"draft_version": d["version"], "reason": reason[:1000], "failing_lines": bad})
    from .template import render
    ans = cases.read_answer(case_id) or {}
    f = dict(m["fields"])
    if f.get("subject", "____") == "____":
        f["subject"] = (ans.get("draft") or {}).get("subject") or "____"
    f["date"] = dt.datetime.now(IST).date()
    text = render(f, [l["sentence"] for l in lines], m["lang"])
    p = cases.write_outbox(case_id, text)
    cases.set_status(case_id, "approved", approved_version=d["version"])
    audit.append_event(case_id, "approve", {"draft_version": d["version"], "override": bool(bad), "mode": mode(),
                                            "model": llm.DEFAULT_MODEL})
    audit.append_event(case_id, "outbox", {"file": "outbox/reply.txt", "bytes": p.stat().st_size,
                                           "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "sent": False})
    return {"status": "approved", "draft_version": d["version"], "override": bool(bad), "outbox_url": f"/api/cases/{case_id}/outbox",
            "text": text}


@app.get("/api/cases/{case_id}/outbox")
def outbox(case_id: str):
    if not _case_or_404(case_id) or not cases.outbox_path(case_id).exists():
        return err(404, "no outbox file")
    return FileResponse(cases.outbox_path(case_id), media_type="text/plain; charset=utf-8", filename=f"reply_{case_id[:8]}.txt")


@app.get("/api/log")
def log(case_id: str = None):
    return list(audit.iter_events(case_id))


app.mount("/", StaticFiles(directory=str(ROOT / "mockup"), html=True), name="ui")