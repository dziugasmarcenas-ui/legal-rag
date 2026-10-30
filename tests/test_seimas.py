"""The Seimas parser is tested on the rules, not on the blocked site.

The site is unreachable to non-browser clients, but the parsing decisions are
what would corrupt the corpus if they were wrong: keeping table-of-contents
lines, or keeping the PDF's syllable-split text.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import ingest_seimas


def test_index_lines_are_rejected():
    assert ingest_seimas.is_index_line("Šio įstatymo priėmimas ................ 12")
    assert not ingest_seimas.is_index_line("Darbuotojams turi būti suteiktos kasmetinės atostogos.")


def test_syllable_split_text_is_rejected():
    broken = "La bai ačiū už klau si mą. At sa kant į pir mą klau si mą, te rei kia pa kar to ti."
    assert not ingest_seimas.looks_clean(broken)

    clean = ("Darbuotojams turi būti suteiktos ne mažiau kaip dvidešimt darbo dienų "
             "kasmetinių atostogų už kiekvienus darbo metus.")
    assert ingest_seimas.looks_clean(clean)


def test_relevant_keeps_context_around_a_keyword():
    lines = [
        "Pirmininkas. Pradedame posėdį.",
        "Seimo narys. Kalbėsime apie darbo užmokesčio didinimą.",
        "Kitas Seimo narys. Pritariu.",
        "Balsavimas. Priimta.",
    ]
    kept = ingest_seimas.relevant(lines)
    assert any("darbo užmokesčio" in block for block in kept)
    assert any("Pradedame posėdį" in block for block in kept)


def test_chunks_stay_under_the_limit():
    blocks = ["x" * 900, "y" * 900, "z" * 900]
    out = ingest_seimas.chunks(blocks)
    assert len(out) == 3
    assert all(len(chunk) <= ingest_seimas.MAX_CHARS + 200 for chunk in out)
