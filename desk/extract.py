"""Text extraction: pypdfium2 for PDFs (no PyMuPDF: AGPL), plain read for .txt."""
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
