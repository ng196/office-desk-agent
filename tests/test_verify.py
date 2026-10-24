from desk.verify import verify_quote, verify_lines

R07 = "नियम 7. सेवानिवृत्ति पर अर्जित अवकाश का नकदीकरण अधिकतम 300 दिन तक अनुमन्य है।"
F101 = "पत्र सं. 12/3/2025-प्रशा., दिनांक 15.10.2025 उनका प्रकरण प्रशासन अनुभाग में विचाराधीन है।"
ARC = {"R-07": [(1, R07)], "F-101": [(1, F101)]}
Q = "अर्जित अवकाश का नकदीकरण"


def test_19_1_verbatim():
    assert verify_quote(Q, "R-07", ARC)["status"] == "verbatim"


def test_19_2_after_norm():
    r = verify_quote("अर्जित\u200d अवकाश का नकदीकरण", "R-07", ARC)
    assert r["status"] == "verbatim_after_norm" and r["verified"]
    nukta = {"R-07": [(1, "क\u093Cानून के अनुसार")]}
    assert verify_quote("\u0958ानून के अनुसार", "R-07", nukta)["status"] == "verbatim_after_norm"


def test_19_3_paraphrase_flag():
    r = verify_quote("अर्जित छुट्टी का नकदीकरण", "R-07", ARC)
    assert r["status"] == "FLAG" and not r["verified"] and r["score"] < 95


def test_19_4_wrong_source():
    r = verify_quote("प्रकरण प्रशासन अनुभाग में विचाराधीन", "R-07", ARC)
    assert r["status"] == "FLAG wrong_source" and r["found_in"] == "F-101"


def test_null_source_flagged():
    assert verify_quote(None, None, ARC)["status"] == "FLAG no_source"


def test_page_note():
    arc = {"X": [(1, "alpha"), (2, "Rule 65 interest on delayed payment")]}
    ln = verify_lines([{"sentence": "s", "source_file": "X", "page": 1, "verbatim_quote": "interest on delayed payment"}], arc)[0]
    assert ln["verified"] and ln["found_page"] == 2 and "page_note" in ln
