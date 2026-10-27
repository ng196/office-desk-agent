from pathlib import Path

from desk.applicability import assess, heading_tokens, letter_tokens, ref_tokens

LETTERS = Path(__file__).parent / "letters"


def test_tokens():
    assert ref_tokens("invoking Section 8(1)(j) of the RTI Act") == {"8(1)(j)"}
    assert ref_tokens("under Rule 65 and FR 56(j)") == {"65", "56(j)"}
    assert ref_tokens("\u0928\u093f\u092f\u092e 65 \u0915\u0947 \u0905\u0902\u0924\u0930\u094d\u0917\u0924") == {"65"}
    assert heading_tokens("65. Interest on delayed payment of gratuity") == {"65"}


def test_matches_against_not_assessed():
    c3 = letter_tokens((LETTERS / "c3_wrong_rti_exemption.txt").read_text(encoding="utf-8"))
    assert assess(c3, "8. Exemption from disclosure of information") == "matches"
    assert assess(c3, "7. Disposal of request") == "against"
    assert assess(c3, None) == "not_assessed"
    assert assess(set(), "65. Interest on delayed payment") == "not_assessed"


def test_c4_letter_rule_vs_pension_rule_heading():
    c4 = letter_tokens((LETTERS / "c4_wrong_rule_cited.txt").read_text(encoding="utf-8"))
    assert "56(j)" in c4
    assert assess(c4, "53. Retirement on completion of qualifying service") == "against"