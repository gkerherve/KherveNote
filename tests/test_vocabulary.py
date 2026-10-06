from khervenote import vocabulary


def test_suggests_acronyms_formulas_hyphenated_and_names():
    notes = ("We polished the LLZO pellets. Measured with ToF-SIMS and LEIS. "
             "The Hall-Petch relation holds. Fitted with Tougaard. Again Tougaard and "
             "Li7La3Zr2O12 from XPS. The sample was clean.")
    got = vocabulary.suggest([notes])
    for w in ("LLZO", "ToF-SIMS", "LEIS", "Hall-Petch", "Tougaard", "Li7La3Zr2O12", "XPS"):
        assert w in got
    assert "The" not in got and "Measured" not in got and "Again" not in got


def test_known_words_are_not_suggested_again_and_merge():
    got = vocabulary.suggest(["XPS and LEIS and XPS"], known="xps")
    assert got == ["LEIS"]
    assert vocabulary.merge("XPS, LEIS", ["leis", "LLZO"]) == "XPS, LEIS, LLZO"
