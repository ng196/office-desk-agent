import pytest

from desk.extract import chunk_page, extract_pages, section_chunks, ExtractError


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


ACT_P9 = """be made as soon as practicable but in no case later than five days from the date of receipt of the application, and the applicant shall be informed immediately about such transfer.
6. Request for obtaining information.—(1) A person, who desires to obtain any information under this Act, shall make a request in writing or through electronic means in English or Hindi
(2) An applicant making request for information shall not be required to give any reason for requesting the information or any other personal details except those that may be necessary for contacting him.
7. Disposal of request.—(1) Subject to the proviso to sub-section (2) of section 5, the Central Public Information Officer shall, as expeditiously as possible, and in any case within thirty days of the receipt of the request, either provide the information or reject the request.
12.7 of Assurances given by a Minister to either House of Parliament, a wrapped line that is not a heading at all here."""
ACT_P10 = """(2) If the Central Public Information Officer fails to give decision on the request within the period specified, he shall be deemed to have refused the request and this text carries on for a while.
8. Exemption from disclosure of information.—(1) Notwithstanding anything contained in this Act, there shall be no obligation to give any citizen,— (a) information, disclosure of which would prejudicially affect the sovereignty and integrity of India, the security, strategic, scientific or economic interests of the State."""
HI = """नियम 7. अर्जित अवकाश का नकदीकरण अधिकतम 300 दिन तक अनुमन्य है और यह पाठ कुछ लंबा रखा गया है ताकि टुकड़ा न्यूनतम लंबाई से बड़ा हो और अलग खंड बने।
नियम 8. अर्धवेतन अवकाश प्रत्येक वर्ष बीस दिन का होगा और यह पाठ भी कुछ लंबा रखा गया है ताकि टुकड़ा न्यूनतम लंबाई से बड़ा हो और अलग खंड बने।"""


def norm_ws(s):
    return " ".join(s.split())


def test_section_chunks_split_on_headings_and_keep_page():
    out = section_chunks([(9, ACT_P9), (10, ACT_P10)])
    starts = [c[:12] for _, c in out]
    assert any(c.startswith("7. Disposal of request") and "thirty days" in c and pg == 9 for pg, c in out)
    assert any(c.startswith("8. Exemption") and pg == 10 for pg, c in out)
    assert not any(c.startswith("12.7 of") for _, c in out), starts
    # the run-over of s.7 onto p.10 is its own piece, cited to p.10; every piece is text of the page it cites
    for pg, c in out:
        assert c in norm_ws({9: ACT_P9, 10: ACT_P10}[pg])
    # nothing lost
    assert norm_ws(" ".join(c for pg, c in out if pg == 9)) == norm_ws(ACT_P9)


def test_section_chunks_hindi_and_oversize_fallback():
    out = section_chunks([(1, HI)], min_chars=50)
    assert [c[:7] for _, c in out] == ["नियम 7.", "नियम 8."]
    big = "5. Long rule.—" + "\n".join("(%d) sub-rule text that goes on and on for the test of size." % i for i in range(60))
    pieces = section_chunks([(3, big)], max_chars=1500)
    assert len(pieces) > 1 and all(len(c) <= 1500 and pg == 3 for pg, c in pieces)
