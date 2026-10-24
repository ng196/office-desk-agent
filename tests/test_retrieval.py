from conftest import doc_ranks, FIX


def test_11_1_file_number_rank1(fixture_db, embedder):
    assert doc_ranks(fixture_db[1], embedder, "12/3/2025-प्रशा.")[0] == "F-101"


def test_11_2_devanagari_digits_top3(fixture_db, embedder):
    assert "F-101" in doc_ranks(fixture_db[1], embedder, "१२/३/२०२५")[:3]


def test_11_3_english_file_number_rank1(fixture_db, embedder):
    assert doc_ranks(fixture_db[1], embedder, "A-12011/5/2024")[0] == "E-22"


def test_11_4_plural_top5(fixture_db, embedder):
    assert "R-07" in doc_ranks(fixture_db[1], embedder, "अवकाशों")[:5]


def test_12_1_cross_lingual_top3(fixture_db, embedder):
    assert "R-07" in doc_ranks(fixture_db[1], embedder, "leave encashment")[:3]


def test_12_2_paraphrase_top5(fixture_db, embedder):
    assert "R-07" in doc_ranks(fixture_db[1], embedder, "छुट्टी के बदले भुगतान")[:5]


def test_12_3_unrelated_not_top10(fixture_db, embedder):
    assert "R-07" not in doc_ranks(fixture_db[1], embedder, "वाहन खरीद", top=10)


def test_12_4_e5_prefixes(embedder):
    embedder.calls.clear()
    embedder.query("x")
    embedder.passages(["y"])
    assert embedder.calls == ["query: x", "passage: y"]


def test_13_2_delete_removes_vectors(tmp_path, embedder):
    from desk.store import connect, add_document, delete_document
    from desk.retrieve import vector_search
    con = connect(tmp_path / "d.db")
    for n in ("F-101", "R-07", "E-22"):
        add_document(con, embedder, FIX / f"{n}.txt", name=n)
    delete_document(con, "F-101")
    ids = vector_search(con, embedder, "12/3/2025-प्रशा. अर्जित अवकाश", n=50)
    files = {con.execute("SELECT file FROM chunks WHERE id=?", (i,)).fetchone()[0] for i in ids}
    assert "F-101" not in files and len(ids) == con.execute("SELECT count(*) FROM chunks").fetchone()[0]


def test_13_3_reopen_same_results(fixture_db, embedder):
    from desk.store import connect
    before = doc_ranks(fixture_db[1], embedder, "leave encashment")
    con2 = connect(fixture_db[0])
    assert doc_ranks(con2, embedder, "leave encashment") == before


def test_reindex_same_file_is_noop(fixture_db, embedder):
    from desk.store import add_document
    assert add_document(fixture_db[1], embedder, FIX / "R-07.txt", name="R-07") == 0


def test_15_3_rerank_deterministic(fixture_db, embedder):
    q = "अर्जित अवकाश नकदीकरण नियम"
    assert doc_ranks(fixture_db[1], embedder, q) == doc_ranks(fixture_db[1], embedder, q)


def test_15_2_english_query_hindi_doc_after_rerank(fixture_db, embedder):
    assert "R-07" in doc_ranks(fixture_db[1], embedder, "rule on encashment of earned leave on retirement")[:3]


def test_max_two_chunks_per_file(tmp_path, embedder):
    from desk.store import connect, add_document
    from desk.retrieve import search
    con = connect(tmp_path / "m.db")
    pages = [(i, f"Rule {i}. Leave encashment is allowed for earned leave, item {i}.") for i in range(1, 6)]
    add_document(con, embedder, None, name="rules", pages=pages, min_page_chars=10)
    add_document(con, embedder, FIX / "E-22.txt", name="E-22")
    hits = search(con, embedder, "leave encashment", top=5)
    assert sum(h["file"] == "rules" for h in hits) == 2 and "E-22" in [h["file"] for h in hits]


def test_statutory_cues_detected():
    from desk.retrieve import statutory_cues
    cues = [c.lower() for c in statutory_cues("Reply within thirty days under Section 7(1) of the Right to Information Act, 2005 and नियम 65")]
    assert "thirty days" in cues and "section 7(1)" in cues and "information act" in cues and "नियम 65" in cues
    assert statutory_cues("Please send my salary slip.") == []


def test_cue_hits_join_rerank_pool(tmp_path, embedder):
    """Exact-phrase cue hits are added to the pool (skipping ones already there); scores are not changed."""
    from desk.store import connect, add_document
    from desk.retrieve import search, cue_phrase_search
    con = connect(tmp_path / "c.db")
    pages = [(i, f"General office circular number {i} about attendance, files and records of the section.") for i in range(1, 30)]
    pages.append((30, "The information shall be provided within thirty days of the receipt of the request."))
    add_document(con, embedder, None, name="mix", pages=pages, min_page_chars=10)
    letter = "Office files and records attendance circular. Reply within thirty days."
    cid30 = con.execute("SELECT id FROM chunks WHERE page=30").fetchone()[0]
    assert cue_phrase_search(con, letter) == [cid30]
    assert cue_phrase_search(con, letter, exclude={cid30}) == []
    assert cue_phrase_search(con, "Office files and records attendance circular.") == []
    t = {}
    hits = search(con, embedder, letter, top=30, candidates=1, max_per_file=30, rerank=False, timings=t)
    assert 30 in [h["page"] for h in hits] and len(hits) == 1 + t["cue_candidates"]


def test_doc_types_table_covers_samples():
    from desk.store import load_doc_types, ROOT_SAMPLES
    table = load_doc_types()
    assert set(table.values()) <= {"rule", "case", "reference"}
    if ROOT_SAMPLES.exists():
        files = {p.name for p in ROOT_SAMPLES.iterdir() if p.suffix.lower() in (".pdf", ".txt")}
        assert files <= set(table), sorted(files - set(table))


def test_split_lists_by_doc_type(tmp_path, embedder):
    """Rules and past cases come back as separate lists, each from its own pool; cue hits go to the rules pool."""
    from desk.store import connect, add_document, retag
    from desk.retrieve import search_split
    con = connect(tmp_path / "s.db")
    add_document(con, embedder, None, name="act.txt", doc_type="rule",
                 pages=[(1, "7. Disposal of request. The information shall be provided within thirty days of the receipt of the request.")], min_page_chars=10)
    add_document(con, embedder, None, name="order.txt", doc_type="case",
                 pages=[(1, "Order: the appellant asked for information; the public authority said the file was missing.")], min_page_chars=10)
    t = {}
    lists = search_split(con, embedder, "My RTI request about a missing file got no reply within thirty days.", rerank=False, timings=t)
    assert [h["file"] for h in lists["rules"]] == ["act.txt"] and [h["file"] for h in lists["cases"]] == ["order.txt"]
    # tag lives in the DB and follows the table on retag
    assert retag(con, table={"act.txt": "rule", "order.txt": "rule"}) == 1
    assert con.execute("SELECT doc_type FROM docs WHERE file='order.txt'").fetchone()[0] == "rule"


def test_reference_files_in_neither_list(tmp_path, embedder):
    from desk.store import connect, add_document
    from desk.retrieve import search_split
    con = connect(tmp_path / "r.db")
    add_document(con, embedder, None, name="gloss.txt", doc_type="reference",
                 pages=[(1, "Glossary: missing file - गुम फाइल; information - सूचना; thirty days - तीस दिन.")], min_page_chars=10)
    lists = search_split(con, embedder, "missing file information thirty days", rerank=False)
    assert lists == {"cases": [], "rules": []}


def test_page_types_table_tags_appendix_pages():
    """Explicit page ranges in doc_types.json: forms / sample letters at the back of rule books are 'case'."""
    from desk.store import load_page_types, page_type
    pt = load_page_types()
    assert page_type("ccs_pension_rules_2021_en.pdf", 106, pages=pt) == "case"  # sample letter
    assert page_type("ccs_pension_rules_2021_en.pdf", 60, pages=pt) == "case"   # FORM 1
    assert page_type("ccs_pension_rules_2021_en.pdf", 46, pages=pt) == "rule"   # Rule 65
    assert page_type("ccs_leave_rules_1972.pdf", 60, pages=pt) == "case"
    assert page_type("csmop_2022_en.pdf", 104, pages=pt) == "case"              # format of D.O. letter
    assert page_type("csmop_2022_en.pdf", 117, pages=pt) == "rule"              # chapter 9 text
    assert page_type("rti_act_2005_en.pdf", 9, pages=pt) == "rule"


def test_appendix_pages_go_to_cases_list(tmp_path, embedder):
    """A page listed in _page_types moves its chunks from the rules list to the past-cases list."""
    from desk.store import connect, add_document, chunk_types
    from desk.retrieve import search_split
    con = connect(tmp_path / "p.db")
    pt = {"book.txt": [(2, 2, "case")]}
    add_document(con, embedder, None, name="book.txt", doc_type="rule", min_page_chars=10, pages=[
        (1, "65. Interest on delayed payment of gratuity. Interest shall be paid where gratuity is delayed."),
        (2, "Sir, I am directed to convey sanction of gratuity and interest on delayed payment. Yours faithfully")])
    types = chunk_types(con, pages=pt)
    assert sorted(types.values()) == ["case", "rule"]
    import desk.retrieve as r
    orig = r.chunk_types
    r.chunk_types = lambda c: chunk_types(c, pages=pt)
    try:
        lists = search_split(con, embedder, "interest on delayed gratuity", top=3, rerank=False)
    finally:
        r.chunk_types = orig
    assert [h["page"] for h in lists["rules"]] == [1] and [h["page"] for h in lists["cases"]] == [2]


def test_rerank_label_at_most_20_tokens():
    from desk.rerank import LABEL_TOKENS, MAX_LEN
    from desk.retrieve import POOL
    assert LABEL_TOKENS == 20 and MAX_LEN == 256 and POOL == {"rules": 16, "cases": 12}
    from desk import rerank as rr
    m = rr.get()
    long = "Rule 65 — Interest on delayed payment of gratuity, pension and family pension where the delay is attributable to administrative lapses of the office"
    short = m.short_label(long)
    assert long.startswith(short) and len(m.tok.encode(short, add_special_tokens=False).ids) <= 20 < len(m.tok.encode(long, add_special_tokens=False).ids)
    assert m.short_label("Rule 7 — Leave") == "Rule 7 — Leave"
