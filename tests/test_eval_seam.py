"""Tests proving the Evaluator seam (D-00a) is a real, swappable boundary.

Task 1 tests `MaterialEval`'s side-to-move-relative symmetry/sign behavior.
Task 2 adds `search_root`/`negamax` behavior tests plus the structural proof
that `ance/search/negamax.py` never imports a concrete evaluator class --
the seam is only "real" (not cosmetic, per project ARCHITECTURE.md
Anti-Pattern 3) if search depends solely on the `Evaluator` Protocol.
"""

from __future__ import annotations

import threading
from pathlib import Path

import chess

from ance.board.position import Position
from ance.eval import tables
from ance.eval.handcrafted import (
    TEMPO_BONUS,
    HandcraftedEval,
    _is_endgame,
    _material_and_pst,
)
from ance.eval.material import PIECE_VALUES, MaterialEval, NaiveEval
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
    result = search_root(
        pos, max_depth=2, evaluator=MaterialEval(), stop_flag=_never_stop()
    )
    assert result.best_move == chess.Move.from_uci("a1a8")


def test_search_root_zero_legal_moves_returns_none() -> None:
    # Fool's Mate FEN (from Plan 01-02's test_has_no_legal_moves_true_for_checkmate).
    fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    pos = Position(chess.Board(fen))
    result = search_root(
        pos, max_depth=2, evaluator=MaterialEval(), stop_flag=_never_stop()
    )
    assert result.best_move is None


def test_search_root_deterministic_tie_break_first_move() -> None:
    pos = Position()
    evaluator = NaiveEval()
    expected = list(pos.board.legal_moves)[0]

    first = search_root(
        pos.copy(), max_depth=1, evaluator=evaluator, stop_flag=_never_stop()
    )
    second = search_root(
        pos.copy(), max_depth=1, evaluator=evaluator, stop_flag=_never_stop()
    )
    assert first.best_move == expected
    assert second.best_move == expected


def test_negamax_module_never_imports_a_concrete_evaluator() -> None:
    source = Path("ance/search/negamax.py").read_text()
    non_comment_source = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "MaterialEval" not in non_comment_source
    assert "NaiveEval" not in non_comment_source


# --- Plan 01-04 Task 1: pinned Simplified Evaluation Function PSTs -------


def test_pst_tables_have_64_entries() -> None:
    for table in (
        tables.PAWN_PST,
        tables.KNIGHT_PST,
        tables.BISHOP_PST,
        tables.ROOK_PST,
        tables.QUEEN_PST,
        tables.KING_MG_PST,
        tables.KING_EG_PST,
    ):
        assert len(table) == 64
        assert all(isinstance(value, int) for value in table)


def test_pawn_pst_is_zero_on_first_and_last_rank() -> None:
    for file in range(8):
        assert tables.PAWN_PST[chess.square(file, 0)] == 0  # rank 1
        assert tables.PAWN_PST[chess.square(file, 7)] == 0  # rank 8


def test_pst_reference_cells_match_pinned_appendix() -> None:
    # 01-RESEARCH.md "Pinned reference cells" -- chosen because each cell
    # differs from its vertically-mirrored counterpart, so a reversed-row
    # transcription error fails loudly here rather than slipping past the
    # two structural checks above.
    assert tables.PAWN_PST[chess.D4] == tables.PAWN_PST[chess.E4] == 20
    assert tables.PAWN_PST[chess.D2] == tables.PAWN_PST[chess.E2] == -20
    assert tables.PAWN_PST[chess.D7] == tables.PAWN_PST[chess.E7] == 50
    assert (
        tables.KNIGHT_PST[chess.A1]
        == tables.KNIGHT_PST[chess.H1]
        == tables.KNIGHT_PST[chess.A8]
        == tables.KNIGHT_PST[chess.H8]
        == -50
    )
    assert (
        tables.KING_EG_PST[chess.D4]
        == tables.KING_EG_PST[chess.E4]
        == tables.KING_EG_PST[chess.D5]
        == tables.KING_EG_PST[chess.E5]
        == 40
    )
    assert tables.KING_EG_PST[chess.B1] == -30
    assert tables.KING_EG_PST[chess.B8] == -40


# --- Plan 01-04 Task 2: material+PST helper, discrete king-table switch --


def test_material_and_pst_helper_symmetric_at_startpos() -> None:
    board = chess.Board()
    assert _material_and_pst(board, chess.WHITE) == _material_and_pst(board, chess.BLACK)


def test_king_table_switches_to_endgame_below_threshold() -> None:
    startpos = chess.Board()
    assert not _is_endgame(startpos)

    kings_and_pawns = chess.Board("4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1")
    assert _is_endgame(kings_and_pawns)

    pawn_subtotal = sum(
        PIECE_VALUES[chess.PAWN] + tables.PAWN_PST[square]
        for square in chess.SquareSet(chess.BB_RANK_2)
    )
    eg_king_contribution = _material_and_pst(kings_and_pawns, chess.WHITE) - pawn_subtotal
    assert eg_king_contribution == tables.KING_EG_PST[chess.E1]

    # Force the same king+pawn skeleton back above the endgame threshold
    # with extra queens, isolating the king's own contribution the same
    # way -- proving the switch is driven by `_is_endgame`, not by the
    # kings-and-pawns FEN shape itself.
    mg_forcing = chess.Board("q3k3/pppppppp/8/8/8/8/PPPPPPPP/Q3K2Q w - - 0 1")
    assert not _is_endgame(mg_forcing)
    queens_subtotal = sum(
        PIECE_VALUES[chess.QUEEN] + tables.QUEEN_PST[square] for square in (chess.A1, chess.H1)
    )
    mg_king_contribution = (
        _material_and_pst(mg_forcing, chess.WHITE) - pawn_subtotal - queens_subtotal
    )
    assert mg_king_contribution == tables.KING_MG_PST[chess.E1]


# --- Plan 01-04 Task 3: positional terms, wiring, swap-seam reinforcement,
# --- post-wiring performance re-benchmark ---------------------------------


def test_startpos_evaluates_to_exact_tempo_bonus() -> None:
    # Material, PST, mobility, and bishop-pair all cancel by symmetry on
    # move one -- only the side-to-move tempo term survives.
    pos = Position()
    assert HandcraftedEval().evaluate(pos) == TEMPO_BONUS


def test_bishop_pair_bonus_applied() -> None:
    two_bishops_fen = "4k3/8/8/8/8/2B1B3/8/4K3 w - - 0 1"
    one_bishop_fen = "4k3/8/8/8/8/4B3/8/4K3 w - - 0 1"

    two_bishops_score = HandcraftedEval().evaluate(Position(chess.Board(two_bishops_fen)))
    one_bishop_score = HandcraftedEval().evaluate(Position(chess.Board(one_bishop_fen)))

    assert two_bishops_score > one_bishop_score


def test_doubled_and_isolated_pawn_penalty() -> None:
    # Both white pawns doubled AND isolated on the d-file.
    doubled_isolated_fen = "4k3/8/8/8/3P4/8/3P4/4K3 w - - 0 1"
    # Same pawn count, spread across adjacent (mutually-supporting, hence
    # non-isolated) files, no doubling.
    distinct_supported_fen = "4k3/8/8/8/3P4/8/2P5/4K3 w - - 0 1"

    doubled_isolated_score = HandcraftedEval().evaluate(
        Position(chess.Board(doubled_isolated_fen))
    )
    distinct_supported_score = HandcraftedEval().evaluate(
        Position(chess.Board(distinct_supported_fen))
    )

    assert doubled_isolated_score < distinct_supported_score


def test_mobility_term_rewards_more_legal_moves() -> None:
    # Same material (one queen, two kings, no pawns) in both positions --
    # White queen centralized in the open (d5) has clearly more legal
    # moves than the same queen cornered (a1), all else equal.
    open_fen = "7k/8/8/3Q4/8/8/8/7K w - - 0 1"
    cornered_fen = "7k/8/8/8/8/8/8/Q6K w - - 0 1"
    assert len(list(chess.Board(open_fen).legal_moves)) > len(
        list(chess.Board(cornered_fen).legal_moves)
    )

    open_score = HandcraftedEval().evaluate(Position(chess.Board(open_fen)))
    cornered_score = HandcraftedEval().evaluate(Position(chess.Board(cornered_fen)))

    assert open_score > cornered_score


def test_mobility_term_no_crash_when_side_to_move_in_check() -> None:
    # White king e1 in check from a rook on a1 -- a null move is illegal
    # here, so the opponent-mobility sub-term must fall back to 0 instead
    # of pushing chess.Move.null() while the side to move is in check.
    fen = "4k3/8/8/8/8/8/8/r3K3 w - - 0 1"
    pos = Position(chess.Board(fen))
    score = HandcraftedEval().evaluate(pos)
    assert isinstance(score, int)


def test_evaluator_swap_handcrafted_vs_material_no_negamax_change() -> None:
    pos = Position()
    material_result = search_root(
        pos.copy(),
        max_depth=2,
        evaluator=MaterialEval(),
        stop_flag=_never_stop(),
    )
    handcrafted_result = search_root(
        pos.copy(),
        max_depth=2,
        evaluator=HandcraftedEval(),
        stop_flag=_never_stop(),
    )
    assert material_result.best_move in pos.board.legal_moves
    assert handcrafted_result.best_move in pos.board.legal_moves

    source = Path("ance/search/negamax.py").read_text()
    non_comment_source = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "HandcraftedEval" not in non_comment_source
    assert "MaterialEval" not in non_comment_source
    assert "NaiveEval" not in non_comment_source
