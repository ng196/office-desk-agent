"""Real-case scenarios (docs/real-cases.md) against the samples/ index. Needs `python -m desk index` first;
live drafting needs LMSTUDIO_API_KEY."""
import json
import re
from pathlib import Path

import pytest

from desk import llm

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "index.db"
CASES = json.loads((Path(__file__).parent / "letters" / "cases.json").read_text(encoding="utf-8"))
need_db = pytest.mark.skipif(not DB.exists(), reason="run `python -m desk index` first")
need_key = pytest.mark.skipif(not llm.api_key(), reason="LMSTUDIO_API_KEY not set")


@pytest.fixture(scope="module")
def con():
    from desk.store import connect
    return connect(DB)


def hit_ok(h, exp):
    return h["file"] == exp["file"] and (not exp.get("text_regex") or re.search(exp["text_regex"], h["text"], re.I | re.S))


@need_db
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_retrieval_recall_at_3(case, con, embedder):
    from desk.extract import extract_pages
    from desk.retrieve import search
    letter = extract_pages(Path(__file__).parent / "letters" / case["letter"])[0][1]
    hits = search(con, embedder, letter, top=3)
    for exp in case["expected"]:
        assert any(hit_ok(h, exp) for h in hits), f"{exp} not in top 3: {[(h['file'], h['page']) for h in hits]}"


@need_db
@need_key
def test_c5_live_draft_cites_rule_65_not_68(con, embedder):
    from desk.cli import answer
    case = next(c for c in CASES if c["id"] == "C5")
    out = answer(con, embedder, Path(__file__).parent / "letters" / case["letter"], lang="en")
    d = out["draft"]
    text = " ".join(l["sentence"] + " " + (l.get("verbatim_quote") or "") for l in d["lines"])
    assert re.search(r"\b(rule|नियम)?\s*65\b", text, re.I) and not re.search(r"\brule\s*68\b", text, re.I)


@need_key
def test_16_1_models_listed():
    assert llm.list_models()
