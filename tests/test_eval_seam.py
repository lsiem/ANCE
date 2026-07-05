"""Tests proving the Evaluator seam (D-00a) is a real, swappable boundary.

Task 1 tests `MaterialEval`'s side-to-move-relative symmetry/sign behavior.
Task 2 adds `search_root`/`negamax` behavior tests plus the structural proof
that `ance/search/negamax.py` never imports a concrete evaluator class --
the seam is only "real" (not cosmetic, per project ARCHITECTURE.md
Anti-Pattern 3) if search depends solely on the `Evaluator` Protocol.
"""

from __future__ import annotations

import random
import threading
from pathlib import Path

import chess

from ance.board.position import Position
from ance.eval.material import MaterialEval, NaiveEval
from ance.search.negamax import search_root


def _never_stop() -> threading.Event:
    """A stop_flag that is never set -- for tests that want an unbounded
    (within the tiny fixed depths used here) search."""
    return threading.Event()


def test_material_eval_symmetric_position_scores_zero() -> None:
    pos = Position()
    assert MaterialEval().evaluate(pos) == 0

    # Push a null move so it's black to move on an otherwise-identical
    # board -- proving side-to-move relative symmetry (D-07), not just
    # "white == black material".
    pos.board.push(chess.Move.null())
    assert MaterialEval().evaluate(pos) == 0


def test_material_eval_reflects_material_difference_stm_relative() -> None:
    # Black is missing its queen.
    fen = "rnb1kbnr/pppp1ppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    white_to_move = Position(chess.Board(fen))
    assert MaterialEval().evaluate(white_to_move) > 0

    black_to_move = Position(chess.Board(fen))
    black_to_move.board.turn = chess.BLACK
    assert MaterialEval().evaluate(black_to_move) < 0


def test_search_root_finds_mate_in_one() -> None:
    pos = Position(chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1"))
    move = search_root(
        pos, depth=2, evaluator=MaterialEval(), stop_flag=_never_stop(), rng=random.Random(0)
    )
    assert move == chess.Move.from_uci("a1a8")


def test_search_root_zero_legal_moves_returns_none() -> None:
    # Fool's Mate FEN (from Plan 01-02's test_has_no_legal_moves_true_for_checkmate).
    fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    pos = Position(chess.Board(fen))
    move = search_root(
        pos, depth=2, evaluator=MaterialEval(), stop_flag=_never_stop(), rng=random.Random(0)
    )
    assert move is None


def test_search_root_tie_break_uses_seeded_rng() -> None:
    pos = Position()
    evaluator = NaiveEval()  # scores everything 0 -> every root move ties

    first = search_root(
        pos.copy(), depth=1, evaluator=evaluator, stop_flag=_never_stop(), rng=random.Random(42)
    )
    second = search_root(
        pos.copy(), depth=1, evaluator=evaluator, stop_flag=_never_stop(), rng=random.Random(42)
    )
    assert first == second  # same seed, freshly re-seeded each time -> same draw

    # A different seed CAN return a different move -- proven across a small
    # deterministic sweep of fixed seeds rather than a single brittle pair,
    # since random.Random's exact draw for any one seed isn't itself part
    # of the contract we're testing (only that varying the seed varies the
    # outcome for a tied field of candidates).
    moves_across_seeds = {
        search_root(
            pos.copy(), depth=1, evaluator=evaluator, stop_flag=_never_stop(), rng=random.Random(seed)
        )
        for seed in range(10)
    }
    assert len(moves_across_seeds) > 1


def test_negamax_module_never_imports_a_concrete_evaluator() -> None:
    source = Path("ance/search/negamax.py").read_text()
    non_comment_source = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "MaterialEval" not in non_comment_source
    assert "NaiveEval" not in non_comment_source
