"""`position`/`ucinewgame` robustness: the `Position` adapter's
startpos/fen/moves handling (unit-level) plus the full `position` ->
`ucinewgame` -> `setoption` -> `ponder`/`debug` command surface driven as a
real piped subprocess (integration-level) -- see 01-02-PLAN.md.

D-10's "reject and keep, never reject and reset" contract is the single
most important behavior proven here: a malformed `position` command must
never corrupt or reset whatever position was previously in play.
"""

from __future__ import annotations

import re

from ance.board.position import Position
from tests.conftest import send_lines
from tests.test_go_bestmove import _read_bestmove

BESTMOVE_RE = re.compile(r"^bestmove ([a-h][1-8][a-h][1-8][qrbn]?|\(none\))$")


def _handshake(engine) -> None:
    engine.send("uci")
    engine.read_line()  # id name
    engine.read_line()  # id author
    engine.read_line()  # uciok


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


def test_malformed_fen_rejected_board_unchanged(engine):
    _handshake(engine)
    send_lines(
        engine,
        [
            "position startpos moves e2e4",
            "position fen not-a-real-fen",
            "go depth 1",
        ],
    )
    line = engine.read_line(timeout=2.0)
    assert line.startswith("info string"), f"expected info string, got: {line!r}"
    line = _read_bestmove(engine, timeout=2.0)
    # A legal black reply proves the board is still at "startpos + e2e4",
    # not corrupted/reset by the malformed second `position` command (D-10).
    move_uci = line.split()[1]
    assert move_uci[1] == "7" or move_uci[1] == "8", (
        f"expected a black-side move (rank 7/8 origin), got: {move_uci!r}"
    )


def test_unknown_leading_token_ignored(engine):
    engine.send("frobnicate 42")
    engine.send("isready")
    assert engine.read_line(timeout=1.0) == "readyok"


def test_ucinewgame_resets_board_to_startpos(engine):
    send_lines(
        engine,
        [
            "position fen 8/8/8/8/8/8/8/K6k w - - 0 1",
            "ucinewgame",
            "go depth 1",
        ],
    )
    line = _read_bestmove(engine, timeout=2.0)
    move_uci = line.split()[1]
    # The king-only endgame FEN's only legal moves all originate from a1
    # (the lone white king). A startpos-reset bestmove can never originate
    # from a1 -- proving `ucinewgame` actually reset the board rather than
    # continuing to search the prior king-only endgame.
    assert not move_uci.startswith("a1"), f"unexpected move: {move_uci!r}"
    assert move_uci != "(none)"


def test_setoption_consumed_without_side_effects(engine):
    engine.send("setoption name Hash value 128")
    engine.send("isready")
    assert engine.read_line(timeout=1.0) == "readyok"


def test_ponder_and_ponderhit_are_noop(engine):
    engine.send("ponder")
    engine.send("ponderhit")
    engine.send("isready")
    assert engine.read_line(timeout=1.0) == "readyok"


def test_debug_off_by_default_no_stderr_output(engine):
    _handshake(engine)
    engine.send("isready")
    assert engine.read_line(timeout=1.0) == "readyok"
    assert engine.has_stderr_output(timeout=0.3) is False


def test_debug_on_enables_stderr_logging(engine):
    engine.send("debug on")
    engine.send("isready")
    assert engine.read_line(timeout=1.0) == "readyok"
    assert engine.has_stderr_output(timeout=1.0) is True
