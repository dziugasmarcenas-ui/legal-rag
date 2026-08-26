from pathlib import Path


INDEX = Path(__file__).parents[1] / "static" / "index.html"


def test_lithuanian_ui_uses_natural_user_facing_language():
    html = INDEX.read_text(encoding="utf-8")

    expected_phrases = (
        "atsakymai su šaltiniais",
        "atsakymą pagrįsime konkrečiu straipsniu",
        "Patikimam atsakymui nepakanka duomenų",
        "Vertinamas atsakymo patikimumas",
        "Sąsajos komponentai pritaikyti",
    )
    literal_phrases = (
        "cituojami atsakymai",
        "pasitikėjimo vartai",
        "Kandidatai perrikiuojami",
        "UI primityvai adaptuoti",
    )

    for phrase in expected_phrases:
        assert phrase in html
    for phrase in literal_phrases:
        assert phrase not in html


def test_lithuanian_answer_instructions_name_the_observed_failures():
    """The answer-language instruction must keep naming the real failures.

    These are not stylistic preferences. Each pair was an actual ungrammatical
    output: a comparative adverb used for people, a dative clause with no verb,
    and a noun phrase missing its head noun. Losing the counter-examples means
    losing the fix, so the contract is that both halves stay.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1]))
    import main

    lt = main.ANSWER_LANGUAGE["lt"]
    for right, wrong in (
        ("jaunesni nei 18 metų", "jauniau nei 18 metų"),
        ("pagimdžius du ar daugiau vaikų", "pagimdžius du ar daugiau“"),
        ("Darbuotojui priklauso 30 darbo dienų", "kategorijoms: 30 darbo dienų"),
    ):
        assert right in lt, f"lost the correct form: {right}"
        assert wrong in lt, f"lost the counter-example: {wrong}"

    assert "pilnais sakiniais" in lt
    assert "trumpai" not in lt, "'trumpai' pushed the model toward fragments"


def test_both_languages_forbid_markdown_headings():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1]))
    import main

    assert "Nerašyk antraščių" in main.ANSWER_LANGUAGE["lt"]
    assert "markdown headings" in main.ANSWER_LANGUAGE["en"]
