import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def embedder():
    from desk.embed import Embedder
    return Embedder()


@pytest.fixture(scope="session")
def fixture_db(tmp_path_factory, embedder):
    from desk.store import connect, add_document
    db = tmp_path_factory.mktemp("idx") / "t.db"
    con = connect(db)
    for p in sorted(FIX.glob("*.txt")):
        add_document(con, embedder, p, name=p.stem)
    return db, con


def doc_ranks(con, embedder, query, top=10):
    from desk.retrieve import search
    return [h["file"] for h in search(con, embedder, query, top=top)]
