"""Web API with a fake engine: no network, no index, no models."""
import pytest
from fastapi.testclient import TestClient

from desk import llm, web

ARC = {"R-07": [(1, "Rule 7. Encashment of earned leave is allowed up to 300 days.")],
       "F-101": [(1, "Office order No. 12/3/2025 on leave encashment.")]}
HITS = {"rules": [{"rank": 1, "file": "R-07", "page": 1, "heading": "7. Encashment of leave", "score": 1.0, "snippet": "Rule 7"}],
        "cases": [{"rank": 1, "file": "F-101", "page": 1, "heading": None, "score": 0.9, "snippet": "Office order"}]}
LINES = [{"sentence": "Leave encashment is allowed up to 300 days.", "source_file": "R-07", "page": 1,
          "verbatim_quote": "allowed up to 300 days"},
         {"sentence": "Your file was traced.", "source_file": "F-101", "page": 1, "verbatim_quote": "file traced in record room"}]


def fake_answer(empty=False, usage=None):
    def answer(con, embedder, path, lang="en", fields=None, chat=None, **kw):
        lists = {"rules": [], "cases": []} if empty else HITS
        user = "INCOMING LETTER: x\n\n" + "\n".join(f"[1] source_file: {h['file']} | page: 1" for t in lists for h in lists[t])
        out = {"letter_file": str(path), "lang": lang, "retrieval_s": 0.1, "total_s": 0.2, **{t: list(v) for t, v in lists.items()}}
        try:
            data, stats = chat([{"role": "system", "content": "s"}, {"role": "user", "content": user}], {})
            out["draft"] = {"summary": "Leave query", "subject": "Leave encashment", "lines": [dict(l) for l in data["lines"]],
                            "llm_stats": stats, "verified_pct": 50.0}
        except llm.LLMError as e:
            out["draft_error"] = str(e)
        return out
    return answer


class FakeCon:
    def close(self):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DESK_MODE", "demo")
    monkeypatch.setenv("DESK_DEMO_PASSCODE", "test-pass")
    monkeypatch.setenv("DESK_WEB_WARM", "0")
    monkeypatch.setattr(web, "open_db", lambda: FakeCon())
    monkeypatch.setattr(web, "answer_fn", fake_answer())
    monkeypatch.setattr(web, "load_archive_fn", lambda con, files: {f: ARC[f] for f in files})
    monkeypatch.setattr(web, "doc_shas_fn", lambda con, files: {f: "sha-" + f for f in files})
    calls = []

    def chat_json(messages, schema, **kw):
        calls.append(messages)
        return {"summary": "s", "subject": "x", "lines": LINES}, {"prompt_tokens": 500, "completion_tokens": 100, "model": "fake"}
    monkeypatch.setattr(llm, "chat_json", chat_json)
    return calls


def login(c, code="test-pass"):
    return c.post("/api/login", json={"passcode": code})


def new_case(c, text="Sir, kindly tell me the leave encashment limit under Rule 7.", lang="en"):
    r = c.post("/api/cases", files={"file": ("letter.txt", text.encode("utf-8"), "text/plain")}, data={"lang": lang, "office": "Demo Office"})
    assert r.status_code == 200, r.text
    cid = r.json()["case_id"]
    assert c.post(f"/api/cases/{cid}/answer").json()["status"] == "queued"  # TestClient runs the background job right after
    return cid


def test_demo_gate_and_health(env):
    with TestClient(web.app) as c:
        h = c.get("/api/health").json()
        assert h["mode"] == "demo" and h["demo_banner"] and "key" not in str(h).lower()
        assert c.get("/api/cases").status_code == 401
        assert login(c, "nope").status_code == 401
        assert c.get("/api/cases").status_code == 401
        r = login(c)
        assert r.status_code == 204 and "httponly" in r.headers["set-cookie"].lower()
        assert c.get("/api/cases").json() == []
        assert c.get("/").status_code == 200


def test_full_path_flag_blocks_then_clerk_fact_then_approve(env):
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
        g = c.get(f"/api/cases/{cid}").json()
        assert g["status"] == "done" and g["summary"] == "Leave query" and g["sources"]["rules"][0]["file"] == "R-07"
        l0, l1 = g["draft"]["lines"]
        assert l0["line_type"] == "cited" and l0["verify"]["verified"] and l0["doc_sha256"] == "sha-R-07"
        assert l0["applicability"] == "matches" and l1["applicability"] == "not_assessed"
        assert l1["verify"]["status"].startswith("FLAG")
        r = c.post(f"/api/cases/{cid}/approve", json={})
        assert r.status_code == 409 and [f["index"] for f in r.json()["failing_lines"]] == [1]
        lines = g["draft"]["lines"]
        lines[1]["line_type"] = "clerk_fact"
        assert c.patch(f"/api/cases/{cid}/draft", json={"lines": lines}).status_code == 422  # clerk_note required
        lines[1]["clerk_note"] = "Seen the movement register myself on 20.10.2026"
        p = c.patch(f"/api/cases/{cid}/draft", json={"lines": lines})
        assert p.status_code == 200 and p.json()["version"] == 2
        a = c.post(f"/api/cases/{cid}/approve", json={})
        assert a.status_code == 200 and a.json()["override"] is False
        txt = c.get(f"/api/cases/{cid}/outbox")
        assert txt.status_code == 200 and "Your file was traced." in txt.text and "[UNVERIFIED]" not in txt.text
        assert "Demo Office" in txt.text
        assert c.get(f"/api/cases/{cid}").json()["status"] == "approved"
        ev = [e["event_type"] for e in c.get(f"/api/log?case_id={cid}").json()]
        assert ev == ["intake", "answer_started", "answer_done", "verify", "draft_edited", "verify", "approve", "outbox"]
        assert c.post(f"/api/cases/{cid}/approve", json={}).status_code == 409  # already approved


def test_override_is_logged(env):
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
        r = c.post(f"/api/cases/{cid}/approve", json={"override_reason": "Officer confirmed by phone"})
        assert r.status_code == 200 and r.json()["override"] is True
        ov = [e for e in c.get(f"/api/log?case_id={cid}").json() if e["event_type"] == "override"]
        assert ov and ov[0]["reason"] == "Officer confirmed by phone" and ov[0]["failing_lines"][0]["index"] == 1


def test_source_not_in_retrieved_blocks(env):
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
        lines = c.get(f"/api/cases/{cid}").json()["draft"]["lines"][:1]
        lines[0]["source_file"] = "X-99"
        c.patch(f"/api/cases/{cid}/draft", json={"lines": lines})
        r = c.post(f"/api/cases/{cid}/approve", json={})
        assert r.status_code == 409 and r.json()["failing_lines"][0]["status"] == "FLAG not_in_retrieved"


def test_no_matching_record_skips_llm_and_blocks_until_clerk_lines(env, monkeypatch):
    monkeypatch.setattr(web, "answer_fn", fake_answer(empty=True))
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
        g = c.get(f"/api/cases/{cid}").json()
        assert g["status"] == "done" and g["no_matching_record"] and g["draft"]["lines"] == [] and env == []
        assert c.post(f"/api/cases/{cid}/approve", json={}).status_code == 409
        std = [{"sentence": "Your letter has been received and the records are being searched.", "line_type": "standard"}]
        assert c.patch(f"/api/cases/{cid}/draft", json={"lines": std}).status_code == 200
        assert c.post(f"/api/cases/{cid}/approve", json={}).status_code == 200


def test_demo_token_cap(env, monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda m, s, **kw: ({"summary": "s", "subject": "x", "lines": LINES},
                                                               {"prompt_tokens": 19000, "completion_tokens": 2000}))
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
        g = c.get(f"/api/cases/{cid}").json()
        assert g["status"] == "error" and g["error"] == "token_or_call_cap"


def test_demo_call_cap(env):
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
        for _ in range(2):
            c.post(f"/api/cases/{cid}/answer")
        assert len(env) == 3
        assert c.post(f"/api/cases/{cid}/answer").status_code == 409 and len(env) == 3


def test_restart_marks_running_jobs_interrupted(env):
    from desk import cases
    with TestClient(web.app) as c:
        login(c)
        cid = new_case(c)
    cases.set_status(cid, "running")
    with TestClient(web.app) as c:
        login(c)
        g = c.get(f"/api/cases/{cid}").json()
        assert g["status"] == "error" and g["error"] == "interrupted_by_restart"


def test_office_mode_refuses_cloud(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError):
        web.check_mode({"DESK_MODE": "office", "DESK_LLM_PROVIDER": "groq"}, provider="groq")
    with pytest.raises(RuntimeError):
        web.check_mode({"DESK_MODE": "office", "DESK_LLM_PROVIDER": "cerebras"}, provider="cerebras")
    with pytest.raises(RuntimeError):
        web.check_mode({"DESK_MODE": "office", "DESK_LLM_PROVIDER": "lmstudio", "LMSTUDIO_URL": "http://10.0.0.5:1234"},
                       provider="lmstudio", base="http://10.0.0.5:1234/v1")
    assert web.check_mode({"DESK_MODE": "office", "DESK_LLM_PROVIDER": "lmstudio"}, provider="lmstudio",
                          base="http://localhost:1234/v1") == "office"
    monkeypatch.setenv("DESK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DESK_MODE", "office")
    monkeypatch.setenv("DESK_WEB_WARM", "0")
    monkeypatch.setattr(llm, "PROVIDER", "groq")
    with pytest.raises(RuntimeError):
        with TestClient(web.app):
            pass


def test_office_mode_needs_no_passcode(env, monkeypatch):
    monkeypatch.setenv("DESK_MODE", "office")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")  # restored after the test
    monkeypatch.setattr(web, "check_mode", lambda *a, **k: "office")
    with TestClient(web.app) as c:
        assert c.post("/api/login", json={}).status_code == 204
        assert c.get("/api/cases").status_code == 200
        assert c.get("/api/health").json()["demo_banner"] is False
    import os
    assert os.environ["HF_HUB_OFFLINE"] == "1"