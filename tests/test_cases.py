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


@need_db
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_retrieval_recall_at_3(case, con, embedder):
    """Each expectation is checked in its own list (rules or past cases), top 3."""
    from desk.evaluate import expected_ok
    from desk.extract import extract_pages
    from desk.retrieve import search_split
    letter = extract_pages(Path(__file__).parent / "letters" / case["letter"])[0][1]
    lists = search_split(con, embedder, letter, top=3)
    for exp in case["expected"]:
        got = [(h["file"], h["page"]) for h in lists[exp["list"]]]
        assert expected_ok(con, lists[exp["list"]], exp), f"{exp} not in {exp['list']} top 3: {got}"


@need_db
def test_indexed_docs_tagged_from_table(con):
    from desk.store import load_doc_types
    table = load_doc_types()
    rows = con.execute("SELECT file, doc_type FROM docs").fetchall()
    assert rows and all(table.get(f) == t for f, t in rows), [r for r in rows if table.get(r[0]) != r[1]]


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
