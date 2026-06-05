from pokebot.matching import best_match, normalize, score, set_codes


def test_normalize_accents_and_synonyms():
    assert normalize("Coffret Dresseur d'Élite — Chaos Ascendant") == "etb chaos ascendant"
    assert "etb" in normalize("ETB Pokémon FR")


def test_set_codes_extracted():
    assert "me04" in set_codes("ETB Chaos Ascendant ME04")


def test_score_same_set_code_boosts():
    s_same = score("ETB Chaos Ascendant ME04", "Elite Trainer Box Chaos Ascendant ME04")
    s_diff = score("ETB Chaos Ascendant ME04", "ETB Chaos Ascendant ME03")
    assert s_same >= 90
    assert s_diff < s_same
    assert s_diff < 80  # code d'extension different => penalise sous le seuil


def test_best_match_threshold():
    cands = [
        ("ETB Chaos Ascendant ME04", {"id": 1}),
        ("Booster Pack Evolving Skies", {"id": 2}),
    ]
    best, sc = best_match("Elite Trainer Box Chaos Ascendant ME04", cands, 80)
    assert best == {"id": 1}
    assert sc >= 80

    none, sc2 = best_match("Coffret totalement different XY99", cands, 80)
    assert none is None
