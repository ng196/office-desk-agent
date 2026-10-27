"""Append-only case log: one JSON event per line in {DESK_DATA_DIR}/audit.jsonl. Past lines are never rewritten."""
import datetime as dt
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ("intake", "answer_started", "answer_done", "draft_edited", "verify", "approve", "override", "outbox")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "IST")
_lock = threading.Lock()


def data_dir() -> Path:
    return Path(os.environ.get("DESK_DATA_DIR") or ROOT / "data")


def log_path() -> Path:
    return data_dir() / "audit.jsonl"


def now_iso() -> str:
    return dt.datetime.now(IST).isoformat(timespec="seconds")


def append_event(case_id, event_type, payload=None) -> dict:
    if event_type not in EVENTS:
        raise ValueError(f"unknown event type {event_type!r}")
    rec = {"ts_iso": now_iso(), "case_id": case_id, "event_type": event_type}
    rec.update({k: v for k, v in (payload or {}).items() if k not in rec})
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False, default=str)
    with _lock, open(p, "a", encoding="utf-8") as f:  # append mode only
        f.write(line + "\n")
    return rec


def iter_events(case_id=None):
    p = log_path()
    if not p.exists():
        return
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if case_id is None or e.get("case_id") == case_id:
                yield e