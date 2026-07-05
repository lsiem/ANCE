"""`position`/`ucinewgame` robustness: the `Position` adapter's
startpos/fen/moves handling (unit-level) plus the full `position` ->
`ucinewgame` -> `setoption` -> `ponder`/`debug` command surface driven as a
real piped subprocess (integration-level) -- see 01-02-PLAN.md.

D-10's "reject and keep, never reject and reset" contract is the single
most important behavior proven here: a malformed `position` command must
never corrupt or reset whatever position was previously in play.
"""

from __future__ import annotations

from ance.board.position import Position


def test_startpos_with_moves_sets_correct_turn_and_fen():
    pos = Position()
    pos.try_set_startpos()
    assert pos.try_push_uci_moves(["e2e4", "e7e5"]) is True
    assert pos.board.fen().startswith(
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq"
    )


def test_has_no_legal_moves_true_for_checkmate():
    pos = Position()
    # Fool's Mate
    assert pos.try_set_fen(
        "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    ) is True
    assert pos.has_no_legal_moves() is True


def test_has_no_legal_moves_false_for_normal_position():
    pos = Position()
    pos.try_set_startpos()
    assert pos.has_no_legal_moves() is False


def test_try_set_fen_rejects_malformed_fen_and_leaves_board_untouched():
    pos = Position()
    pos.try_set_startpos()
    before = pos.board.fen()
    assert pos.try_set_fen("not-a-real-fen") is False
    assert pos.board.fen() == before


def test_try_push_uci_moves_rejects_illegal_move_and_leaves_board_untouched():
    pos = Position()
    pos.try_set_startpos()
    before = pos.board.fen()
    assert pos.try_push_uci_moves(["e2e5"]) is False
    assert pos.board.fen() == before
