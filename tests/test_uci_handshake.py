"""Walking-skeleton proof: the UCI handshake never hangs and a bare `go`
returns exactly one legal `bestmove`, verified as a real piped subprocess
(never manual typing) -- see 01-01-PLAN.md.
"""

from __future__ import annotations

import re

from tests.test_go_bestmove import _read_bestmove

BESTMOVE_RE = re.compile(r"^bestmove [a-h][1-8][a-h][1-8][qrbn]?$")


def test_uci_handshake(engine):
    engine.send("uci")
    assert engine.read_line() == "id name ANCE 0.1"
    assert engine.read_line() == "id author Lasse Siemoneit"
    assert engine.read_line() == "uciok"


def test_isready_before_anything(engine):
    # isready arriving as the very first line (before `uci`) must still
    # be answered promptly -- this is the whole point of UCI-02.
    engine.send("isready")
    assert engine.read_line(timeout=1.0) == "readyok"


def test_bare_go_returns_bestmove(engine):
    engine.send("uci")
    engine.read_line()  # id name
    engine.read_line()  # id author
    engine.read_line()  # uciok
    engine.send("isready")
    engine.read_line()  # readyok

    engine.send("go")
    _read_bestmove(engine, timeout=4.0)

    engine.send("quit")
    exit_code = engine.wait(timeout=2.0)
    assert exit_code == 0
