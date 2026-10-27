import json

import pytest

from desk import audit


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_DATA_DIR", str(tmp_path))
    return tmp_path


def test_append_and_read_back(tmp_data):
    audit.append_event("c1", "intake", {"sha256": "abc"})
    audit.append_event("c2", "intake", {})
    audit.append_event("c1", "approve", {"draft_version": 2, "case_id": "spoofed", "event_type": "spoofed"})
    ev = list(audit.iter_events("c1"))
    assert [e["event_type"] for e in ev] == ["intake", "approve"]
    assert ev[1]["case_id"] == "c1" and ev[1]["draft_version"] == 2 and ev[0]["ts_iso"].endswith("+05:30")
    assert len(list(audit.iter_events())) == 3


def test_append_only_never_rewrites(tmp_data):
    audit.append_event("c1", "intake", {"n": 1})
    first = (tmp_data / "audit.jsonl").read_text(encoding="utf-8")
    audit.append_event("c1", "verify", {"n": 2})
    after = (tmp_data / "audit.jsonl").read_text(encoding="utf-8")
    assert after.startswith(first) and len(after.splitlines()) == 2
    assert json.loads(after.splitlines()[0])["n"] == 1


def test_unknown_event_type_rejected():
    with pytest.raises(ValueError):
        audit.append_event("c1", "email_sent", {})