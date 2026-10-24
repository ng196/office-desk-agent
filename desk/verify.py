"""Quote verification (tests.md 19.x): exact, then after normalisation, then RapidFuzz.

Proves the quote exists in the cited file; it does NOT prove the sentence follows from it.
"""
from rapidfuzz import fuzz

from .normalize import norm

FUZZY_MIN = 95.0
VERIFIED = {"verbatim", "verbatim_after_norm", "fuzzy_match"}


def _locate(quote, pages):
    """pages: [(page, text)]. Returns (status, page, score) for the best match in this file."""
    nq = norm(quote)
    for pg, txt in pages:
        if quote in txt:
            return "verbatim", pg, 100.0
    for pg, txt in pages:
        if nq in norm(txt):
            return "verbatim_after_norm", pg, 100.0
    best = (None, 0.0)
    for pg, txt in pages:
        s = fuzz.partial_ratio(nq, norm(txt))
        if s > best[1]:
            best = (pg, s)
    return ("fuzzy_match" if best[1] >= FUZZY_MIN else "FLAG"), best[0], round(best[1], 1)


def verify_quote(quote, cited_file, archive):
    """archive: {file: [(page, text)]}. Returns dict(status, verified, found_page, score, found_in)."""
    if not quote or not cited_file:
        return {"status": "FLAG no_source", "verified": False, "found_page": None, "score": 0.0, "found_in": None}
    if cited_file not in archive:
        return {"status": "FLAG unknown_source", "verified": False, "found_page": None, "score": 0.0, "found_in": None}
    status, pg, score = _locate(quote, archive[cited_file])
    if status in VERIFIED:
        return {"status": status, "verified": True, "found_page": pg, "score": score, "found_in": cited_file}
    for other, pages in archive.items():  # real quote, wrong file?
        if other == cited_file:
            continue
        st, opg, osc = _locate(quote, pages)
        if st in VERIFIED:
            return {"status": "FLAG wrong_source", "verified": False, "found_page": opg, "score": osc, "found_in": other}
    return {"status": "FLAG", "verified": False, "found_page": pg, "score": score, "found_in": None}


def verify_lines(lines, archive):
    out = []
    for ln in lines:
        r = verify_quote(ln.get("verbatim_quote"), ln.get("source_file"), archive)
        if r["verified"] and ln.get("page") not in (None, r["found_page"]):
            r["page_note"] = f"quote is on page {r['found_page']}, not {ln.get('page')}"
        out.append({**ln, **r})
    return out
