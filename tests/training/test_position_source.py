"""Tests for deterministic position generation and run manifest logging."""

from __future__ import annotations

import json

from training.label.position_source import generate_position_set, synthetic_game_id
from training.run_manifest import record_event


def test_generate_position_set_is_deterministic() -> None:
    first = generate_position_set(n_games=5, seed=1)
    second = generate_position_set(n_games=5, seed=1)
    assert first == second


def test_generate_position_set_entries_well_formed() -> None:
    samples = generate_position_set(n_games=5, seed=2)
    assert samples
    game_ids = set()
    for entry in samples:
        assert entry["fen"]
        assert entry["game_id"]
        game_ids.add(entry["game_id"])
    assert len(game_ids) == 5


def test_synthetic_game_id_format() -> None:
    assert synthetic_game_id(7) == "fresh-000007"


def test_record_event_appends_without_clobbering(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    record_event(str(manifest), event="first", depth=6)
    record_event(str(manifest), event="second", depth=8)
    events = json.loads(manifest.read_text())
    assert len(events) == 2
    assert events[0]["event"] == "first"
    assert events[1]["depth"] == 8
