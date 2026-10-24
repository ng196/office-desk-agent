import pytest

from desk.extract import chunk_page, extract_pages, ExtractError


def make_pdf(path, lines):
    """Tiny one-page PDF (Helvetica, ASCII only) built by hand: no extra dependency."""
    text = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({l}) Tj 0 -16 Td" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(text)} >>\nstream\n{text}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    x = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF".encode()
    path.write_bytes(out)


def test_2_2_english_pdf_exact(tmp_path):
    p = tmp_path / "E-22.pdf"
    make_pdf(p, ["No. A-12011/5/2024-Estt.", "Subject: Leave encashment"])
    pages = extract_pages(p)
    assert pages[0][0] == 1 and "No. A-12011/5/2024-Estt." in pages[0][1]


def test_txt_is_page_1(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("विषय: अर्जित अवकाश का नकदीकरण", encoding="utf-8")
    assert extract_pages(p) == [(1, "विषय: अर्जित अवकाश का नकदीकरण")]


def test_2_4_bad_pdf_clean_error(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"%PDF-1.4 not really")
    with pytest.raises(ExtractError):
        extract_pages(p)


@pytest.mark.skip(reason="2.1 needs a Unicode Hindi PDF fixture with an embedded Devanagari font; none built yet")
def test_2_1_hindi_pdf():
    pass


def test_chunks_bounded():
    text = "\n\n".join(["वाक्य " * 50 + "।"] * 10 + ["word " * 600])
    cs = chunk_page(text, max_chars=1200)
    assert cs and all(len(c) <= 1200 for c in cs)
    assert "".join(cs).replace(" ", "") == text.replace(" ", "").replace("\n", "")
