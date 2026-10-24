import pytest

from desk.retrieve import rrf


def test_14_1():
    out = rrf([["d1", "d2", "d3"], ["d3", "d1", "d4"]], k=60)
    assert [d for d, _ in out] == ["d1", "d3", "d2", "d4"]
    assert [round(s, 5) for _, s in out] == pytest.approx([0.03252, 0.03227, 0.01613, 0.01587], abs=1e-5)


def test_14_2_one_list_empty():
    assert [d for d, _ in rrf([[], ["b", "a", "c"]])] == ["b", "a", "c"]


def test_14_3_ties_by_id():
    assert [d for d, _ in rrf([["b"], ["a"]])] == ["a", "b"]
