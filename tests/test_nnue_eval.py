"""EVAL-03 / Phase 5 Plan 05-01: NNUE evaluator swap-in contracts.

Covers D-01..D-16 as applicable to the eval path:
- D-01/D-02/D-05/D-07/D-08: env-selectable NnueEval + default weights
- D-03/D-06: fail-fast on invalid ANCE_EVAL / missing weights
- D-13: torch↔numpy exact integer cp parity
- D-14: king-only symmetric positions score 0
- D-15: color-mirror + STM flip equality
- D-16: Stockfish sign agreement (optional binary)
- EVAL-01: search never imports concrete evaluators
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import chess
import pytest

from ance.board.position import Position

SYMMETRIC_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
ENGINE_MODULE = "ance"

# Stub count for Task 1; expanded to 40 in Task 3.
_PARITY_SAMPLE_FENS = [
    chess.STARTING_FEN,
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
]

_DEFAULT_NET = Path("ance/eval/nnue/net.safetensors")


def test_nnue_loads_default_net() -> None:
    """NnueEval loads default net and returns int cp for startpos."""
    from ance.eval.nnue.eval import NnueEval

    nnue = NnueEval()
    score = nnue.evaluate(Position())
    assert isinstance(score, int)


def test_invalid_ance_eval_exits_nonzero() -> None:
    """ANCE_EVAL=bogus exits non-zero; stderr lists allowed values (D-03)."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANCE_EVAL", "ANCE_DEBUG", "ANCE_NNUE_PATH")
    }
    env["ANCE_EVAL"] = "bogus"
    proc = subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE],
        input="quit\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert proc.returncode != 0
    assert "allowed" in proc.stderr.lower()


def test_symmetric_positions_score_zero() -> None:
    """King-only symmetric FEN scores exactly 0 for white and black STM (D-14)."""
    from ance.eval.nnue.eval import NnueEval

    nnue = NnueEval()
    assert nnue.evaluate(Position(chess.Board(SYMMETRIC_FEN))) == 0
    black_stm = chess.Board(SYMMETRIC_FEN)
    black_stm.turn = chess.BLACK
    assert nnue.evaluate(Position(black_stm)) == 0


@pytest.mark.torch
@pytest.mark.parametrize("fen", _PARITY_SAMPLE_FENS)
def test_torch_numpy_parity_sample(fen: str) -> None:
    """Torch int cp equals NnueEval int cp on sample FENs (D-13 stub)."""
    pytest.importorskip("torch")
    from ance.eval.nnue.eval import NnueEval
    from tests.nnue_parity_helpers import (
        load_torch_nnue_from_safetensors,
        numpy_cp_int,
        torch_cp_int,
    )

    assert _DEFAULT_NET.is_file(), f"missing default net: {_DEFAULT_NET}"
    model = load_torch_nnue_from_safetensors(str(_DEFAULT_NET))
    nnue = NnueEval()
    assert torch_cp_int(model, fen) == numpy_cp_int(nnue, fen)


def test_negamax_never_imports_concrete_nnue_or_handcrafted() -> None:
    """negamax.py non-comment lines omit HandcraftedEval and NnueEval."""
    source = Path("ance/search/negamax.py").read_text()
    non_comment = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "NnueEval" not in non_comment
    assert "HandcraftedEval" not in non_comment


def test_color_mirror_stm_flip() -> None:
    """Color-mirror + STM flip scores match (D-15) — completed in Task 3."""
    pytest.skip("Task 3")


def test_stockfish_sign_agreement() -> None:
    """Stockfish sign agrees on won/lost positions (D-16) — completed in Task 3."""
    if shutil.which("stockfish") is None:
        pytest.skip("stockfish binary not on PATH")
    pytest.skip("Task 3")
