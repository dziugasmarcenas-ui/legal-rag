"""The validity snapshot is what stands between the corpus and dead law."""

import json
import sys

from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import check_act_status


ROOT = Path(__file__).parents[1]


def test_the_snapshot_covers_every_served_act():
    snapshot = json.loads((ROOT / "data" / "act_status.json").read_text(encoding="utf-8"))
    records = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    serving = check_act_status.indexed_acts(records)
    missing = [i for i in serving if i not in snapshot["acts"]]
    assert missing == [], f"acts with no recorded status: {missing}"


def test_no_served_act_is_marked_repealed():
    snapshot = json.loads((ROOT / "data" / "act_status.json").read_text(encoding="utf-8"))
    records = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    serving = set(check_act_status.indexed_acts(records))
    repealed = {i for i, s in snapshot["acts"].items() if s["state"] == "repealed"}
    assert serving & repealed == set()


def test_the_check_fails_when_a_served_act_is_repealed(tmp_path, monkeypatch):
    snapshot = {
        "checked_at": date.today().isoformat(),
        "acts": {"act-1": {"state": "repealed", "since": "2020-01-01"}},
    }
    records = [{"source": "Test", "act_id": "act-1", "citation": "Test, 1 p."}]
    (tmp_path / "sources.json").write_text(json.dumps(records))
    (tmp_path / "act_status.json").write_text(json.dumps(snapshot))
    monkeypatch.setattr(check_act_status, "SOURCES", tmp_path / "sources.json")
    monkeypatch.setattr(check_act_status, "STATUS", tmp_path / "act_status.json")
    monkeypatch.setattr(check_act_status, "REPEALED", tmp_path / "none.json")
    assert check_act_status.main([]) == 1
