"""The edition window is a correctness property, not metadata.

These are the cases that matter: the last day is still valid, the next day is
not, and the warning names the cutoff instead of saying "stale".
"""

import sys

from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import edition


def test_last_day_in_force_is_not_expired():
    assert edition.is_expired("2026-10-31", date(2026, 10, 31)) is False


def test_the_day_after_is_expired():
    assert edition.is_expired("2026-10-31", date(2026, 11, 1)) is True


def test_days_left_counts_whole_days_and_goes_negative():
    assert edition.days_left("2026-10-31", date(2026, 10, 30)) == 1
    assert edition.days_left("2026-10-31", date(2026, 11, 2)) == -2


def test_no_warning_while_the_edition_holds():
    assert edition.warning("2026-10-31", date(2026, 10, 30)) is None


def test_warning_names_the_cutoff():
    text = edition.warning("2026-10-31", date(2026, 11, 5))
    assert "2026-10-31" in text
    assert "expired" in text


def test_the_interface_shows_the_expiry_it_is_told_about():
    """The banner is driven by /health, not by a date compiled into the page."""
    html = (Path(__file__).parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "HEALTH.edition_expired" in html
    assert 'id="stale"' in html
