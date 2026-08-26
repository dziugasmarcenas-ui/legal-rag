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
