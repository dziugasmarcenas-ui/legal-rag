"""Constitutional Court parsing is tested on its header rules.

The decisions are the reason the case graph is no longer ECHR-only, and the two
things that would corrupt it are a wrong date (the heading is full of statute
dates) and a lost case number (one document renders "Byla" as "By1a").
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import ingest_kt

HEADER = """Byla Nr. 19/2017
LIETUVOS RESPUBLIKOS KONSTITUCINIS TEISMAS
Lietuvos Respublikos vardu
NUTARIMAS
Dėl ligos ir motinystės socialinio draudimo įstatymo 16 straipsnio nuostatų
2018 m. gruodžio 19 d. Nr. KT23-N13/2018
Vilnius
"""


def test_the_decision_date_is_not_a_statute_date():
    text = HEADER + "Dėl 2001 m. sausio 25 d. nutarimo Nr. 86 nuostatų.\n"
    assert ingest_kt.date_of(text) == "2018-12-19"


def test_a_misrendered_byla_still_yields_the_case_number():
    text = HEADER.replace("Byla Nr.", "By1a Nr.")
    assert ingest_kt.case_of(text) == "19/2017"


def test_a_case_number_is_recovered_from_the_body_when_the_header_lacks_one():
    text = "LIETUVOS RESPUBLIKOS KONSTITUCINIS TEISMAS\nNUTARIMAS\n" \
           "... išnagrinėjo konstitucinės justicijos bylą Nr. 44/2009 pagal ...\n"
    assert ingest_kt.case_of(text) == "44/2009"


def test_only_labour_passages_are_kept():
    assert ingest_kt.is_labour(
        "Darbo kodekso 59 straipsnis numato atleidimą; darbuotojas turi teisę "
        "į išeitinę išmoką."
    )
    assert not ingest_kt.is_labour(
        "Konstitucinis Teismas nagrinėjo prašymą dėl proceso atnaujinimo."
    )
