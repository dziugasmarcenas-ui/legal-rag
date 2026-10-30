"""Committee conclusions are the published half of the committee record.

Transcripts are not published; conclusions are, and they are where a committee
states why it proposes an amendment. Parsing must survive the header variants
("KOMITETO IŠVADA" vs "PAPILDOMO KOMITETO I Š V A D O S") and both date forms.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import ingest_committee

SPACED = """LIETUVOS RESPUBLIKOS SEIMO
Žmogaus teisių komitetas
PAPILDOMO KOMITETO
I Š V A D O S
DĖL LIETUVOS RESPUBLIKOS DARBO KODEKSO 23 STRAIPSNIO PAKEITIMO ĮSTATYMO PROJEKTO
Nr. XVP-463
2025-09-24 Nr. 112-P-24
Vilnius
"""


def test_spaced_header_is_recognised():
    assert ingest_committee.CONCLUSION.search(SPACED)


def test_iso_date_is_used_when_present():
    assert ingest_committee.date_of(SPACED) == "2025-09-24"


def test_title_names_the_committee_and_the_bill():
    title = ingest_committee.title_of(SPACED)
    assert "Žmogaus teisių komitetas" in title
    assert "DARBO KODEKSO" in title


def test_lithuanian_date_is_the_fallback():
    text = "KOMITETO IŠVADA dėl projekto\n2025 m. spalio 21 d.\nVilnius\n"
    assert ingest_committee.date_of(text) == "2025-10-21"
