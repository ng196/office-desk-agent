"""Case store under {DESK_DATA_DIR}/cases/{case_id}/: inbound file, meta.json, letter.txt, answer.json,
archive_snapshot.json, drafts/v{n}.json, outbox/reply.txt."""
import hashlib
import json
import re
import threading
import uuid
from pathlib import Path

from .audit import data_dir, now_iso

STATUSES = ("queued", "running", "done", "error", "approved")
LINE_TYPES = ("cited", "clerk_fact", "standard")
FIELD_KEYS = ("ref_no", "office", "to", "signatory", "subject")
_ID = re.compile(r"^[0-9a-f]{32}$")
_lock = threading.RLock()


class CaseNotFound(KeyError):
    pass


def cases_dir() -> Path:
    return data_dir() / "cases"


def case_dir(case_id) -> Path:
    if not _ID.match(str(case_id)):
        raise CaseNotFound(case_id)
    d = cases_dir() / case_id
    if not d.is_dir():
        raise CaseNotFound(case_id)
    return d


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def create_case(upload_path, lang="en", mode="demo", fields=None, filename=None) -> str:
    data = Path(upload_path).read_bytes()
    case_id = uuid.uuid4().hex
    d = cases_dir() / case_id
    d.mkdir(parents=True)
    suffix = Path(filename or upload_path).suffix.lower()
    suffix = suffix if suffix in (".pdf", ".txt") else ".txt"
    (d / f"inbound{suffix}").write_bytes(data)
    f = {k: (fields or {}).get(k) or "____" for k in FIELD_KEYS}
    meta = {"case_id": case_id, "sha256": hashlib.sha256(data).hexdigest(), "lang": lang if lang in ("en", "hi") else "en",
            "mode": mode, "status": "queued", "created_ts": now_iso(), "filename": Path(filename or upload_path).name,
            "fields": f, "error": None, "no_matching_record": False, "retrieved_files": [], "llm_calls": 0, "llm_tokens": 0}
    _write_json(d / "meta.json", meta)
    return case_id


def inbound_path(case_id) -> Path:
    return next(case_dir(case_id).glob("inbound.*"))


def get_case(case_id) -> dict:
    return _read_json(case_dir(case_id) / "meta.json")


def update_meta(case_id, **changes) -> dict:
    with _lock:
        meta = get_case(case_id)
        meta.update(changes)
        _write_json(case_dir(case_id) / "meta.json", meta)
        return meta


def set_status(case_id, status, **extra) -> dict:
    if status not in STATUSES:
        raise ValueError(status)
    return update_meta(case_id, status=status, **extra)


def list_cases() -> list:
    out = []
    if cases_dir().exists():
        for d in cases_dir().iterdir():
            m = _read_json(d / "meta.json")
            if m:
                out.append(m)
    return sorted(out, key=lambda m: m["created_ts"], reverse=True)


def save_draft_version(case_id, lines) -> int:
    for ln in lines:
        if ln.get("line_type") not in LINE_TYPES:
            raise ValueError(f"line_type must be one of {LINE_TYPES}")
    with _lock:
        dd = case_dir(case_id) / "drafts"
        dd.mkdir(exist_ok=True)
        v = len(list(dd.glob("v*.json"))) + 1
        _write_json(dd / f"v{v}.json", {"version": v, "ts_iso": now_iso(), "lines": lines})
        return v


def latest_draft(case_id):
    dd = case_dir(case_id) / "drafts"
    vs = sorted((int(p.stem[1:]) for p in dd.glob("v*.json")), reverse=True) if dd.exists() else []
    return _read_json(dd / f"v{vs[0]}.json") if vs else None


def write_letter_text(case_id, text):
    (case_dir(case_id) / "letter.txt").write_text(text, encoding="utf-8")


def read_letter_text(case_id) -> str:
    p = case_dir(case_id) / "letter.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def write_answer(case_id, result):
    _write_json(case_dir(case_id) / "answer.json", result)


def read_answer(case_id):
    return _read_json(case_dir(case_id) / "answer.json")


def write_archive(case_id, archive):
    _write_json(case_dir(case_id) / "archive_snapshot.json", archive)


def read_archive(case_id) -> dict:
    """JSON stores [page, text] lists; verify_lines wants [(int page, text)]."""
    raw = _read_json(case_dir(case_id) / "archive_snapshot.json", {})
    return {f: [(int(p), t) for p, t in pages] for f, pages in raw.items()}


def outbox_path(case_id) -> Path:
    return case_dir(case_id) / "outbox" / "reply.txt"


def write_outbox(case_id, text) -> Path:
    p = outbox_path(case_id)
    p.parent.mkdir(exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p