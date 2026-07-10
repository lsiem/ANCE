"""Depth-vs-depth harness contracts and slow ordering proof (D-14)."""

from __future__ import annotations

from dataclasses import dataclass

import chess
import pytest

from ance.board.position import Position
from ance.eval.handcrafted import HandcraftedEval
from ance.tools import depth_vs_depth_match as depth_match


@dataclass
class _TerminalBoard:
    raw_result: str
    game_over: bool = True
    turn: chess.Color = chess.WHITE

    def is_game_over(self) -> bool:
        return self.game_over

    def result(self) -> str:
        return self.raw_result


@pytest.mark.parametrize(
    ("deep_plays_white", "raw_result", "expected"),
    [
        (True, "1-0", "win"),
        (True, "0-1", "loss"),
        (True, "1/2-1/2", "draw"),
        (False, "1-0", "loss"),
        (False, "0-1", "win"),
        (False, "1/2-1/2", "draw"),
    ],
)
def test_game_outcome_is_from_deeper_side_perspective(
    monkeypatch: pytest.MonkeyPatch,
    deep_plays_white: bool,
    raw_result: str,
    expected: str,
) -> None:
    board = _TerminalBoard(raw_result)
    monkeypatch.setattr(depth_match, "Position", lambda: type("Pos", (), {"board": board})())
    monkeypatch.setattr(depth_match, "_apply_opening", lambda pos, line: None, raising=False)

    outcome = depth_match.play_depth_match_game(
        shallow_depth=2,
        deep_depth=3,
        evaluator=HandcraftedEval(),
        deep_plays_white=deep_plays_white,
        seed=0,
    )

    assert outcome == expected


@pytest.mark.parametrize("deep_plays_white", [True, False])
def test_halfmove_cap_is_a_deeper_perspective_draw(
    monkeypatch: pytest.MonkeyPatch, deep_plays_white: bool
) -> None:
    board = _TerminalBoard("*", game_over=False)
    monkeypatch.setattr(depth_match, "Position", lambda: type("Pos", (), {"board": board})())
    monkeypatch.setattr(depth_match, "_apply_opening", lambda pos, line: None, raising=False)

    outcome = depth_match.play_depth_match_game(
        shallow_depth=2,
        deep_depth=3,
        evaluator=HandcraftedEval(),
        deep_plays_white=deep_plays_white,
        seed=0,
        max_halfmoves=0,
    )

    assert outcome == "draw"


def test_two_deeper_side_wins_tally_as_two_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes = iter(["win", "win"])
    calls: list[tuple[bool, int, int]] = []

    def play_spy(
        shallow_depth: int,
        deep_depth: int,
        evaluator: HandcraftedEval,
        deep_plays_white: bool,
        seed: int,
        max_halfmoves: int,
    ) -> str:
        calls.append((deep_plays_white, seed, max_halfmoves))
        return next(outcomes)

    monkeypatch.setattr(depth_match, "play_depth_match_game", play_spy)

    result = depth_match.run_depth_match(
        shallow_depth=2,
        deep_depth=3,
        n_games=2,
        evaluator=HandcraftedEval(),
        seed=17,
        max_halfmoves=40,
    )

    assert result == {
        "wins": 2,
        "losses": 0,
        "draws": 0,
        "score_rate": 1.0,
        "n_games": 2,
    }
    assert calls == [(True, 17, 40), (False, 18, 40)]


def test_opening_selection_is_reproducible_and_varies_by_seed() -> None:
    assert depth_match._opening_for_seed(0) == depth_match._opening_for_seed(0)
    assert depth_match._opening_for_seed(0) != depth_match._opening_for_seed(1)


def test_every_configured_opening_is_legal_and_four_plies() -> None:
    assert len(depth_match.OPENING_LINES) >= 8
    for line in depth_match.OPENING_LINES:
        pos = Position()
        depth_match._apply_opening(pos, line)
        assert len(line) == 4
        assert len(pos.board.move_stack) == len(line)


def test_non_positive_game_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="n_games"):
        depth_match.run_depth_match(
            shallow_depth=2,
            deep_depth=3,
            n_games=0,
            evaluator=HandcraftedEval(),
        )


@pytest.mark.slow
def test_deeper_search_scores_at_least_fifty_percent() -> None:
    """Depth 3 vs depth 2 over 30 games — deeper side must score >= 50%.

    Plan 02-10 owns this standalone evidence run with a 45-minute budget.
    """
    result = depth_match.run_depth_match(
        shallow_depth=2,
        deep_depth=3,
        n_games=30,
        evaluator=HandcraftedEval(),
        max_halfmoves=80,
    )
    assert result["score_rate"] >= 0.5, (
        f"deeper side scored {result['score_rate']:.1%} "
        f"({result['wins']}W/{result['draws']}D/{result['losses']}L over {result['n_games']} games)"
    )
