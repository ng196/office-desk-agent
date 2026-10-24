import datetime as dt

import pytest

from desk.template import EN_ORDER, HI_ORDER, TemplateError, render

F = {"ref_no": "12/3/2025-प्रशा.", "office": "Office X", "to": "Shri A", "subject": "S", "signatory": "B",
     "reference": "R", "date": dt.date(2025, 10, 15)}


def _in_order(text, order):
    pos = [text.find("BODY" if k == "<body>" else k) for k in order]
    return all(p >= 0 for p in pos) and pos == sorted(pos)


def test_21_1_hindi_order():
    assert _in_order(render(F, ["BODY"], "hi"), HI_ORDER)


def test_21_2_english_order():
    assert _in_order(render(F, ["BODY"], "en"), EN_ORDER)


def test_21_3_missing_date():
    with pytest.raises(TemplateError):
        render({**F, "date": None}, ["x"], "en")


def test_21_4_dates():
    assert "15.10.2025" in render(F, ["x"], "hi")
    assert "15th October, 2025" in render(F, ["x"], "en")
