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
    monkeypatch.delenv("LMSTUDIO_API_KEY", raising=False)
    monkeypatch.setattr(llm, "api_key", lambda: None)
    try:
        llm.list_models()
    except llm.LLMError as e:
        assert "not set" in str(e)
