"""Text normalisation for Hindi/English matching (tests.md rows 10.x).

Our own small step: NFC, split precomposed nukta letters, drop ZWJ/ZWNJ,
Devanagari digits -> ASCII, collapse whitespace. Display text is never changed.
"""
import re
import unicodedata

_NUKTA = {chr(c): unicodedata.normalize("NFD", chr(c)) for c in range(0x0958, 0x0960)}
_DIGITS = {ord(chr(0x0966 + i)): str(i) for i in range(10)}
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u00ad"), None)
_QUOTES = {ord(a): b for a, b in zip("\u2018\u2019\u201c\u201d\u2013\u2014\u00a0", "''\"\"-- ")}
_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    """Normalise for matching. Idempotent: norm(norm(x)) == norm(x)."""
    t = unicodedata.normalize("NFC", text or "")
    t = "".join(_NUKTA.get(ch, ch) for ch in t)  # 0958-095F: always base + nukta
    t = t.translate(_ZW).translate(_DIGITS).translate(_QUOTES)
    return _WS.sub(" ", t).strip().lower()


_SENT = re.compile(r"(?<=[\u0964\u0965.?!])\s+")


def sentences(text: str) -> list[str]:
    return [s for s in (x.strip() for x in _SENT.split(text or "")) if s]


# Light Hindi suffix stripper (plural/oblique) so "अवकाशों" finds "अवकाश".
_HI_SUFFIXES = sorted(["ियों", "ियाँ", "ियां", "ाओं", "ाएँ", "ाएं", "ओं", "ों", "ें", "ाँ", "ां", "िया"], key=len, reverse=True)
_TOKEN = re.compile(r"[0-9a-z\u0900-\u0963\u0970-\u097f]+")


def stem(tok: str) -> str:
    if tok and "\u0900" <= tok[0] <= "\u097f":
        for s in _HI_SUFFIXES:
            if tok.endswith(s) and len(tok) - len(s) >= 2:
                return tok[: -len(s)]
    return tok


def tokens(text: str) -> list[str]:
    """Normalised, stemmed tokens. Used for both index and query (FTS5 sees space-joined tokens)."""
    return [stem(t) for t in _TOKEN.findall(norm(text))]
