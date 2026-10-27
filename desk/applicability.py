"""Applicability signal (no LLM): does the rule/section number the letter talks about match the cited source's heading?

Quote found != correct rule (C3/C4). Returns "matches" | "against" | "not_assessed"; the clerk judges the rest."""
import re

# "Rule 65", "Section 8(1)(j)", "s. 7(1)", "FR 56(j)", "Article 14", Hindi niyam / dhara + number
_REF = re.compile(r"(?:\b(?:rules?|sections?|sec\.|s\.|articles?|art\.|FR|SR|para(?:graph)?)\s*|"
                  r"(?:\u0928\u093f\u092f\u092e|\u0927\u093e\u0930\u093e|\u0905\u0928\u0941\u091a\u094d\u091b\u0947\u0926)\s*)"
                  r"(\d{1,3}[A-Z]?(?:\s*\(\s*[0-9a-z]{1,4}\s*\))*)", re.I)
_LEAD = re.compile(r"^\s*(\d{1,3}[A-Z]?)\s*[.)]\s")  # heading "65. Interest on delayed payment ..."


def _base(tok):
    return re.match(r"\d+[A-Za-z]?", tok).group(0).lower()


def ref_tokens(text) -> set:
    """Rule/section numbers mentioned in text, normalised ("8(1)(j)")."""
    return {re.sub(r"\s+", "", m.group(1)).lower() for m in _REF.finditer(text or "")}


def heading_tokens(heading) -> set:
    toks = ref_tokens(heading)
    m = _LEAD.match(heading or "")
    if m:
        toks.add(m.group(1).lower())
    return toks


def letter_tokens(letter_text) -> set:
    """Same statutory cues retrieval uses, plus any rule/section number in the letter."""
    from .retrieve import statutory_cues
    return ref_tokens(" ".join(statutory_cues(letter_text or ""))) | ref_tokens(letter_text)


def assess(letter_toks, heading) -> str:
    """letter_toks: set from letter_tokens(); heading: the cited hit's section heading (or None)."""
    if not letter_toks:
        return "not_assessed"
    h = heading_tokens(heading)
    if not h:
        return "not_assessed"
    return "matches" if {_base(t) for t in letter_toks} & {_base(t) for t in h} else "against"