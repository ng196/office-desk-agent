"""CLI.  python -m desk index [samples]   |   python -m desk answer LETTER [--lang hi|en] [--json out.json]"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "index.db"


def load_archive(con, files):
    arc = {}
    for f in files:
        pages = {}
        for pg, txt in con.execute("SELECT page, text FROM chunks WHERE file=? ORDER BY id", (f,)):
            pages.setdefault(pg, []).append(txt)
        arc[f] = [(pg, " ".join(t)) for pg, t in sorted(pages.items())]
    return arc


def answer(con, embedder, letter_path, lang="en", top=6, fields=None, use_llm=True, chat=None):
    from .extract import extract_pages
    from .retrieve import search, top_files
    t0 = time.perf_counter()
    letter = "\n".join(t for _, t in extract_pages(letter_path))
    hits = search(con, embedder, letter, top=top)
    t_ret = time.perf_counter() - t0
    out = {"letter_file": str(letter_path), "lang": lang, "retrieval_s": round(t_ret, 2),
           "top_files": top_files(hits),
           "hits": [{k: h[k] for k in ("rank", "chunk_id", "file", "page", "score", "in_keyword", "in_vector", "snippet")} for h in hits]}
    if use_llm:
        from . import draft, llm
        kw = {"chat": chat} if chat else {}
        try:
            out["draft"] = draft.make_draft(letter, hits, load_archive(con, {h["file"] for h in hits}), lang=lang, fields=fields, **kw)
        except llm.LLMError as e:
            out["draft_error"] = str(e)
    out["total_s"] = round(time.perf_counter() - t0, 2)
    return out


def readable(out):
    L = [f"Letter: {out['letter_file']}  (retrieval {out['retrieval_s']} s, total {out['total_s']} s)", "", "Closest past files / rules:"]
    for h in out["hits"]:
        L.append(f"  {h['rank']}. {h['file']}  p.{h['page']}  — {h['snippet'][:160]}")
    d = out.get("draft")
    if d:
        L += ["", f"Summary: {d['summary']}", "", "Draft lines:"]
        for i, ln in enumerate(d["lines"], 1):
            mark = "OK " if ln["verified"] else "!! "
            L.append(f"  {mark}{i}. {ln['sentence']}")
            L.append(f"       source: {ln.get('source_file')} p.{ln.get('page')} [{ln['status']}] quote: \"{(ln.get('verbatim_quote') or '')[:120]}\"")
        L += ["", f"Quotes verified: {d['verified_pct']}%", "", "---- Draft letter ----", d["letter"]]
    elif out.get("draft_error"):
        L += ["", f"Draft skipped: {out['draft_error']}"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="desk")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index", help="index an archive folder (PDF/txt)")
    pi.add_argument("folder", nargs="?", default=str(ROOT / "samples"))
    pa = sub.add_parser("answer", help="letter file in -> top files + cited draft")
    pa.add_argument("letter")
    pa.add_argument("--lang", choices=["en", "hi"], default="en")
    pa.add_argument("--top", type=int, default=6)
    pa.add_argument("--json", help="also write the full JSON here")
    pa.add_argument("--no-llm", action="store_true", help="retrieval only")
    for k in ("ref-no", "office", "to", "signatory", "reference", "date"):
        pa.add_argument(f"--{k}")
    sub.add_parser("models", help="list models loaded in LM Studio")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if a.cmd == "models":
        from . import llm
        print("\n".join(llm.list_models()))
        return 0
    from .embed import Embedder
    from .store import connect, index_folder
    Path(a.db).parent.mkdir(parents=True, exist_ok=True)
    con, emb = connect(a.db), Embedder()
    if a.cmd == "index":
        t0 = time.perf_counter()
        n = index_folder(con, emb, a.folder)
        print(f"done: {n} new chunks in {time.perf_counter() - t0:.1f} s -> {a.db}")
        return 0
    fields = {k: v for k, v in {"ref_no": a.ref_no, "office": a.office, "to": a.to, "signatory": a.signatory,
                                "reference": a.reference, "date": a.date}.items() if v}
    out = answer(con, emb, a.letter, lang=a.lang, top=a.top, fields=fields, use_llm=not a.no_llm)
    print(readable(out))
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
