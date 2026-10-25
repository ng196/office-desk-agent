import json

import jsonschema

from desk import draft

HITS = [{"file": "R-07", "page": 1, "text": "नियम 7. अर्जित अवकाश का नकदीकरण अधिकतम 300 दिन तक अनुमन्य है।"},
        {"file": "F-101", "page": 1, "text": "पत्र सं. 12/3/2025-प्रशा. प्रकरण प्रशासन अनुभाग में विचाराधीन है।"}]
ARC = {h["file"]: [(h["page"], h["text"])] for h in HITS}
FIELDS = {"ref_no": "1/2/2025", "office": "O", "to": "T", "signatory": "S", "date": "2025-10-15"}


def fake_chat(reply):
    seen = {}

    def chat(messages, schema, **kw):
        seen["messages"], seen["schema"] = messages, schema
        jsonschema.validate(reply, schema)  # 18.1: what we accept must match the schema
        return json.loads(json.dumps(reply)), {"wall_s": 0.0}
    return chat, seen


def test_18_1_and_18_3_cites_rule():
    reply = {"summary": "s", "subject": "अर्जित अवकाश", "lines": [
        {"sentence": "नकदीकरण 300 दिन तक है।", "source_file": "R-07", "page": 1, "verbatim_quote": "अधिकतम 300 दिन तक"}]}
    chat, seen = fake_chat(reply)
    d = draft.make_draft("letter", HITS, ARC, lang="hi", fields=FIELDS, chat=chat)
    assert seen["schema"]["properties"]["lines"]["items"]["required"] == ["sentence", "source_file", "page", "verbatim_quote"]
    assert d["lines"][0]["verified"] and d["verified_pct"] == 100.0
    assert "source_file: R-07 | page: 1" in seen["messages"][1]["content"]
    assert d["letter"].index("पत्र सं.") < d["letter"].index("नकदीकरण 300") < d["letter"].index("भवदीय")


def test_18_2_source_not_retrieved_flagged():
    reply = {"summary": "s", "subject": "x", "lines": [
        {"sentence": "a", "source_file": "Z-99", "page": 1, "verbatim_quote": "q"}]}
    d = draft.make_draft("letter", HITS, ARC, fields=FIELDS, chat=fake_chat(reply)[0])
    assert not d["lines"][0]["verified"] and d["lines"][0]["status"].startswith("FLAG")


def test_18_4_null_source_marked():
    reply = {"summary": "s", "subject": "x", "lines": [
        {"sentence": "We will reply soon.", "source_file": None, "page": None, "verbatim_quote": None}]}
    d = draft.make_draft("letter", HITS, ARC, fields=FIELDS, chat=fake_chat(reply)[0])
    assert d["lines"][0]["status"] == "FLAG no_source" and "[UNVERIFIED]" in d["letter"]


def test_paraphrased_quote_unverified():
    reply = {"summary": "s", "subject": "x", "lines": [
        {"sentence": "a", "source_file": "R-07", "page": 1, "verbatim_quote": "अर्जित छुट्टी का नकदीकरण"}]}
    d = draft.make_draft("letter", HITS, ARC, fields=FIELDS, chat=fake_chat(reply)[0])
    assert d["verified_pct"] == 0.0


def test_key_never_in_error(monkeypatch):
    from desk import llm
    monkeypatch.setattr(llm, "api_key", lambda: None)
    try:
        llm.list_models()
    except llm.LLMError as e:
        assert "not set" in str(e)


def test_draft_gets_both_lists():
    reply = {"summary": "s", "subject": "x", "lines": [
        {"sentence": "नकदीकरण 300 दिन तक है।", "source_file": "R-07", "page": 1, "verbatim_quote": "अधिकतम 300 दिन तक"}]}
    chat, seen = fake_chat(reply)
    d = draft.make_draft("letter", {"cases": [HITS[1]], "rules": [HITS[0]]}, ARC, lang="hi", fields=FIELDS, chat=chat)
    msg = seen["messages"][1]["content"]
    assert "RULES (" in msg and "PAST CASES (" in msg
    assert "[1] source_file: F-101" in msg and "[2] source_file: R-07" in msg
    assert d["lines"][0]["verified"]


def test_source_number_in_source_file_is_resolved():
    """Live qwen 4B wrote source_file "[2]" (the source number); it maps to that numbered source and verifies."""
    reply = {"summary": "s", "subject": "x", "lines": [
        {"sentence": "a", "source_file": "[2]", "page": 1, "verbatim_quote": "प्रशासन अनुभाग में विचाराधीन"},
        {"sentence": "b", "source_file": "[9]", "page": 1, "verbatim_quote": "q"}]}
    d = draft.make_draft("letter", HITS, ARC, fields=FIELDS, chat=fake_chat(reply)[0])
    assert d["lines"][0]["source_file"] == "F-101" and d["lines"][0]["verified"]
    assert not d["lines"][1]["verified"]


def test_parse_json_strips_think_and_fences():
    from desk import llm
    assert llm.parse_json('<think>x</think>\n```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Here: {"a": [1, 2]} done') == {"a": [1, 2]}


def test_json_schema_rejected_falls_back_to_strict_prompt(monkeypatch):
    from desk import llm

    class Resp:
        def __init__(self, code, payload=None, text=""):
            self.status_code, self._p, self.text = code, payload, text

        def json(self):
            return self._p
    calls = []

    def post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        if "response_format" in json:
            return Resp(400, text='{"message": "response_format json_schema not supported"}')
        return Resp(200, {"choices": [{"message": {"content": '{"summary": "s", "subject": "x", "lines": []}'}}],
                          "usage": {"completion_tokens": 10}})
    monkeypatch.setattr(llm, "api_key", lambda: "dummy")
    monkeypatch.setattr(llm.requests, "post", post)
    data, stats = llm.chat_json([{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}], {"type": "object"})
    assert data["subject"] == "x" and stats["json_schema_fallback"] is True
    assert len(calls) == 2 and "JSON Schema" in calls[1]["messages"][0]["content"]


def test_load_env_does_not_override(tmp_path, monkeypatch):
    from desk import llm
    p = tmp_path / ".env"
    p.write_text("# c\nDESK_T1=fromfile\nDESK_T2=fromfile\nDESK_T3=\n", encoding="utf-8")
    monkeypatch.setenv("DESK_T1", "already")
    monkeypatch.delenv("DESK_T2", raising=False)
    monkeypatch.delenv("DESK_T3", raising=False)
    llm.load_env(p)
    import os
    assert os.environ["DESK_T1"] == "already" and os.environ["DESK_T2"] == "fromfile" and "DESK_T3" not in os.environ
    monkeypatch.delenv("DESK_T2")
