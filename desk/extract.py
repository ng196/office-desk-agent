"""Text extraction: pypdfium2 for PDFs (no PyMuPDF: AGPL), plain read for .txt."""
import re
from pathlib import Path
import unicodedata


class ExtractError(Exception):
    pass


def extract_pages(path) -> list[tuple[int, str]]:
    """Return [(page_no starting at 1, NFC text)]. A .txt file is page 1."""
    p = Path(path)
    if p.suffix.lower() == ".txt":
        return [(1, unicodedata.normalize("NFC", p.read_text(encoding="utf-8", errors="replace")))]
    if p.suffix.lower() != ".pdf":
        raise ExtractError(f"unsupported file type: {p.suffix}")
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(str(p))
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise ExtractError("encrypted") from e
        raise ExtractError(f"unreadable pdf: {e}") from e
    out = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            tp = page.get_textpage()
            txt = tp.get_text_range().replace("\r\n", "\n").replace("\r", "\n")
            out.append((i + 1, unicodedata.normalize("NFC", txt)))
            tp.close()
            page.close()
    finally:
        pdf.close()
    return out


def chunk_page(text: str, max_chars: int = 1200, min_chars: int = 200) -> list[str]:
    """Split a page into paragraph chunks of up to max_chars, merging short paragraphs."""
    paras = [" ".join(x.split()) for x in text.split("\n\n")]
    if len(paras) == 1:  # many PDFs have no blank lines: fall back to lines
        paras = [" ".join(x.split()) for x in text.split("\n")]
    chunks, cur = [], ""
    for para in filter(None, paras):
        while len(para) > max_chars:  # hard split long paragraph at a space
            cut = para.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(para[:cut].strip())
            para = para[cut:].strip()
        if len(cur) + len(para) + 1 <= max_chars:
            cur = f"{cur} {para}".strip()
        else:
            chunks.append(cur)
            cur = para
        if len(cur) >= min_chars and cur.endswith((".", "\u0964", ":", ";")):
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


# A section/rule heading at the start of a line: "7. Disposal of request", "65. Interest on ...", "12.5. Requests",
# "Rule 65", "Section 7", "धारा 7", "नियम 65" (ASCII or Devanagari digits). The title must start with a capital
# letter, "(" or Devanagari, so "12.7 of Assurances" (a wrapped line) is not a heading.
HEADING = re.compile(r"^[ \t]*(?:(?:Rule|Section|Article|धारा|नियम)[ \t]*)?[0-9०-९]{1,3}[A-Z]?(?:\.[0-9]{1,3})*\.?[ \t]*[—–-]?[ \t]*[A-Z(\u0900-\u097F]",
                     re.M)


def section_chunks(pages, max_chars: int = 1500, min_chars: int = 200) -> list[tuple[int, str]]:
    """Chunk an Act/Rules file at section/rule headings. Returns [(page, text)].

    A section that runs over a page break gives one piece per page (each piece is text of the page it cites,
    so quotes verify against that page). A piece longer than max_chars falls back to paragraph chunks;
    a piece shorter than min_chars is merged into the previous piece on the same page."""
    out = []
    for pg, txt in pages:
        starts = sorted({0, *(m.start() for m in HEADING.finditer(txt))})
        pieces = [txt[a:b] for a, b in zip(starts, starts[1:] + [len(txt)])]
        merged = []  # a piece shorter than min_chars joins the previous piece on the same page
        for raw in pieces:
            if merged and len(" ".join(raw.split())) < min_chars:
                merged[-1] += raw
            else:
                merged.append(raw)
        for raw in merged:
            flat = " ".join(raw.split())
            if flat:
                out += [(pg, c) for c in ([flat] if len(flat) <= max_chars else chunk_page(raw))]
    return out
