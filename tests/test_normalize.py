from desk.normalize import norm, sentences, tokens


def test_10_1_nukta_precomposed_and_decomposed():
    assert norm("\u0958") == norm("\u0915\u093C") == "\u0915\u093C"


def test_10_2_zwj_removed():
    assert norm("क्\u200dष") == "क्ष"


def test_10_3_sentences():
    assert len(sentences("यह पत्र है। कृपया देखें।")) == 2


def test_10_4_devanagari_digits_index_key():
    assert norm("१२/३/२०२५") == "12/3/2025"


def test_idempotent():
    for s in ["\u0958 क्\u200dष १२/३", "  No. A-12011/5/2024-Estt.  ", "अवकाशों"]:
        assert norm(norm(s)) == norm(s)


def test_plural_stem():
    assert tokens("अवकाशों") == tokens("अवकाश")
