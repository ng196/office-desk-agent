import pytest

from desk import cases


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_DATA_DIR", str(tmp_path))
    return tmp_path


def _letter(tmp_path, text="Sir, my pension is late."):
    p = tmp_path / "in.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_create_case_meta_and_inbound(tmp_path):
    cid = cases.create_case(_letter(tmp_path), lang="hi", fields={"ref_no": "1/2"})
    m = cases.get_case(cid)
    assert m["status"] == "queued" and m["lang"] == "hi" and len(m["sha256"]) == 64
    assert m["fields"]["ref_no"] == "1/2" and m["fields"]["office"] == "____"
    assert cases.inbound_path(cid).read_text(encoding="utf-8").startswith("Sir")
    assert [c["case_id"] for c in cases.list_cases()] == [cid]


def test_draft_versions_bump_and_latest(tmp_path):
    cid = cases.create_case(_letter(tmp_path))
    assert cases.latest_draft(cid) is None
    assert cases.save_draft_version(cid, [{"sentence": "a", "line_type": "cited"}]) == 1
    assert cases.save_draft_version(cid, [{"sentence": "b", "line_type": "standard"}]) == 2
    assert cases.latest_draft(cid)["lines"][0]["sentence"] == "b"
    with pytest.raises(ValueError):
        cases.save_draft_version(cid, [{"sentence": "c", "line_type": "guess"}])


def test_archive_round_trip_gives_tuples(tmp_path):
    cid = cases.create_case(_letter(tmp_path))
    cases.write_archive(cid, {"R-07": [(46, "65. Interest on delayed payment")]})
    assert cases.read_archive(cid) == {"R-07": [(46, "65. Interest on delayed payment")]}


def test_outbox_and_status(tmp_path):
    cid = cases.create_case(_letter(tmp_path))
    p = cases.write_outbox(cid, "\u0938\u0947\u0935\u093e \u092e\u0947\u0902,\nreply")
    assert p.read_text(encoding="utf-8").endswith("reply")
    assert cases.set_status(cid, "approved")["status"] == "approved"
    with pytest.raises(ValueError):
        cases.set_status(cid, "sent")


def test_bad_case_id_is_not_found():
    with pytest.raises(cases.CaseNotFound):
        cases.get_case("../../etc")