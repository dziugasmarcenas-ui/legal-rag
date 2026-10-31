"""A reference the model invents must be visible, not silently accepted."""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import citations


RESULTS = [
    {"article": "59", "citation": "59", "title": "t", "text": "x"},
    {"article": "126", "citation": "126", "title": "t", "text": "x"},
]


def test_supported_references_are_reported_as_supported():
    check = citations.verify("Pagal Darbo kodekso 59 straipsnį darbdavys...", RESULTS)
    assert check["cited"] == ["59"]
    assert check["supported"] == ["59"]
    assert check["unsupported"] == []


def test_an_invented_article_is_flagged():
    check = citations.verify("Pagal 77 straipsnį ir 59 straipsnį...", RESULTS)
    assert check["unsupported"] == ["77"]


def test_numbers_that_are_not_article_references_are_ignored():
    check = citations.verify("Nuo 2023 m. sausio 1 d. taikoma 1 245 eurų.", RESULTS)
    assert check["cited"] == []


def test_part_level_references_are_recognised():
    check = citations.verify("Pagal 72-1 straipsnį...", RESULTS)
    assert check["unsupported"] == ["72-1"]


def test_a_refusal_has_nothing_to_check():
    assert citations.verify("", RESULTS)["unsupported"] == []
