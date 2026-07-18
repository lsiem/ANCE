"""EVAL-03 / Phase 5 Plan 05-01: NNUE evaluator swap-in contracts.

Covers D-01..D-16 as applicable to the eval path:
- D-01/D-02/D-05/D-07/D-08: env-selectable NnueEval + default weights
- D-03/D-06: fail-fast on invalid ANCE_EVAL / missing weights
- D-13: torch↔numpy exact integer cp parity
- D-14: symmetric positions score 0 (startpos) + STM agreement
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
import chess.engine
import pytest

from ance.board.position import Position

SYMMETRIC_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
ENGINE_MODULE = "ance"
_DEFAULT_NET = Path("ance/eval/nnue/net.safetensors")

# 32 FENs: deterministic seed=42 subsample of Phase 4 bounded val split
# (val_fraction=0.05, seed=42 → 697 positions) from merged_samples.json.
_VAL_SUBSAMPLE_FENS = [
    "r1bqk1nr/p1pp1ppp/2n1p3/1p6/Pb2PP2/1P4P1/2PP3P/RNBQKBNR b KQkq - 1 7",
    "r2qk1nr/p1pp1ppp/b3p1n1/1p6/PbB1PP2/BP4PP/R1PPN3/1N1QK2R b Kkq - 4 12",
    "rnbqk1nr/pppp1p2/3bp2p/6p1/2P2B2/3P4/PP2PPPP/RN1QKBNR w KQkq - 2 5",
    "r3kbnr/p4ppp/n2p4/1pp1pP2/1P2P1P1/P2P4/b1P2K1P/RNBQ1BNq b kq - 1 12",
    "r1b1k1r1/ppp1n2p/3pp1p1/2n2pq1/P1P1PPP1/2QP4/1P1N2Rb/RN2KB2 w q - 0 20",
    "rn1qkb1r/p3pp2/1pp4p/3p2p1/1P6/5NPb/PBPPPP2/RN1QKBR1 w Qkq - 2 10",
    "2r1kb1r/p1pq3p/b3p1Nn/np1N4/4PpQ1/6P1/PPPP1P1P/R1BK1B1R w k - 1 15",
    "rn1q1bnr/p1ppk2p/5pQ1/2P1p3/1p4b1/NP4P1/P2PPP1P/R1B1KBNR w KQ - 1 10",
    "r1b1kr2/p2p1p1p/n2Q2pn/1P2p3/4P2P/NP3N2/2PK1PPR/R1B2B2 b - - 0 17",
    "r1bqk1nr/6b1/n1ppp2p/pp3pp1/1PP2P2/4PQ2/P2PN1PP/RN1K1B1R b kq - 1 12",
    "2b2bn1/r1nkr3/2pPpq1p/pp3p2/1P3Pp1/2N1P1QP/P2PN1PR/R1K2B2 w - - 2 20",
    "rnb1kbnr/2q5/pp2ppp1/2pp3p/Q1PP2P1/4P2N/PP3P1P/RNBK1B1R b kq - 3 12",
    "rnbqkbnr/5pp1/2pp3p/pp2p3/3P4/BP3P2/P1PQP1PP/RN2KBNR b KQkq - 1 7",
    "rn2kbnr/p4p2/b1pp4/1p4p1/3PpBq1/NPPQ4/P3PP1P/R3KB1R b KQkq - 1 12",
    "r2qk2r/1ppnn1bp/3ppp2/p1N3P1/1PP5/P6N/1RbPP1PP/2BQKBR1 b kq - 2 12",
    "rnbqk1nr/p1p4p/1p2ppp1/3p4/Pb1PP3/R1Q5/2P2PPP/1NB1KBNR b Kkq - 1 7",
    "r1b1kb1r/3pqpp1/nppQp2p/pB1R2N1/2n5/P1P1P3/1P2KPPP/RNB5 b kq - 3 12",
    "rq2kb1r/3n1p1N/1p1pp2P/pp4p1/2Q1P3/2P3PB/RP1P1P1n/1NB1K2R w - - 4 20",
    "1r3br1/pb1pk2p/2p3p1/1p3pN1/qn4n1/2PPP3/RP2NPPP/2B1KB1R w K - 4 20",
    "rnb2bnr/p2k1p2/3pp3/Npp4p/3P2pq/P2K1P2/RPPBP1BP/3Q2NR b - - 1 12",
    "rnbqkb1r/pp1ppppp/7n/2p5/5P1P/BP6/P1PPP1P1/RN1QKBNR w KQkq - 3 5",
    "rn3br1/pN3p2/4k1pp/2ppp3/q2P1Bn1/2P2N1b/1P2PPPR/R2QKB2 w Q - 0 15",
    "rnb1kbnr/1pp2p2/3qp1p1/QN1p4/2P4p/P7/1P1PPPPP/R1B1KBNR b KQkq - 2 7",
    "r2k3r/3npp2/3qb1pb/pP5p/4nP2/P2P4/1B1N2PP/R2K1BNR w - - 2 20",
    "r1b1k2r/2pqbpp1/p3pn2/1pnpP2Q/1P3P1p/3B3P/P1PP2P1/RNB1K1NR b kq - 0 12",
    "rn3kn1/3p2p1/b1p1p3/p1b1p1qr/1p1P2Pp/1P5Q/P1P1NPKP/R1B2BNR w - - 4 20",
    "rnbqk2r/ppp2pp1/3p1n2/B1b4p/1PP3PP/3p1PR1/P2KP3/RN1Q1BN1 b - - 0 12",
    "r1bqk2r/pppn1pp1/1P1p4/6np/1BP3PP/3K1PRB/P3P3/RN1Qb1N1 b - - 2 17",
    "rnb1k1nr/pp3p1B/2p1p2p/qN1p2p1/1P3P2/2b1P2P/P1P1K1PR/1RB1Q1N1 w kq - 1 15",
    "rn5r/ppp1kp1n/4Q2p/2P2bp1/1b1PpqPP/5N2/PP1P1PB1/RNB1K1R1 b - - 2 17",
    "rn2kbnr/p2ppp2/b7/2p1qBpp/1pPPP3/6P1/PPQ2P1P/RNB1K1NR w KQkq - 2 10",
    "rn1n3r/ppp3pp/2b1kp1Q/b3p3/P1p1P1PR/5N2/3P1P2/RNB1KB2 w Q - 1 15",
]

# 8 manual tactical FENs (D-13)
_TACTICAL_FENS = [
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5",
    "6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1",
    "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "2kr3r/pppq1ppp/2nbbn2/3pp3/3PP3/2NBBN2/PPPQ1PPP/2KR3R w - - 0 1",
    "8/8/8/4k3/8/4K3/4Q3/8 w - - 0 1",
    "8/8/8/4k3/8/4K3/4q3/8 b - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
]

_PARITY_FENS = _VAL_SUBSAMPLE_FENS + _TACTICAL_FENS

_COLOR_MIRROR_FENS = [
    "rnbqkbnr/pppp1ppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1",
    "8/8/8/3k4/3Q4/3K4/8/8 w - - 0 1",
    "rnbq1rk1/ppp2ppp/3b1n2/3p4/3P4/2N2N2/PPP1BPPP/R1BQK2R w KQ - 0 7",
    "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
]

# 4 clearly won / 4 clearly lost from White's perspective (D-16)
_SF_WON_FENS = [
    "6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1",  # mate in 1
    "8/8/8/4k3/8/4K3/4Q3/8 w - - 0 1",  # KQ vs K
    "4k3/8/8/8/8/8/8/Q3K3 w - - 0 1",  # queen up
    "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1",  # mating net
]
_SF_LOST_FENS = [
    "r3k3/8/8/8/8/8/5ppp/6K1 b q - 0 1",  # black mates / rook up
    "8/8/8/4K3/8/4k3/4q3/8 b - - 0 1",  # black has queen
    "q3k3/8/8/8/8/8/8/4K3 w - - 0 1",  # white to move, queen down
    "4k3/8/8/8/8/8/8/q3K3 w - - 0 1",  # white to move, queen down
]


def _stripped_env(**overrides: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANCE_EVAL", "ANCE_DEBUG", "ANCE_NNUE_PATH")
    }
    env.update(overrides)
    return env


def test_nnue_loads_default_net() -> None:
    """NnueEval loads default net and returns int cp for startpos."""
    from ance.eval.nnue.eval import NnueEval

    nnue = NnueEval()
    score = nnue.evaluate(Position())
    assert isinstance(score, int)


def test_invalid_ance_eval_exits_nonzero() -> None:
    """ANCE_EVAL=bogus exits non-zero; stderr lists allowed values (D-03)."""
    proc = subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE],
        input="quit\n",
        capture_output=True,
        text=True,
        env=_stripped_env(ANCE_EVAL="bogus"),
        timeout=10,
    )
    assert proc.returncode != 0
    assert "allowed" in proc.stderr.lower()


def test_ance_eval_nnue_isready() -> None:
    """ANCE_EVAL=nnue accepts UCI isready (D-01/D-05)."""
    proc = subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE],
        input="uci\nisready\nquit\n",
        capture_output=True,
        text=True,
        env=_stripped_env(ANCE_EVAL="nnue"),
        timeout=15,
    )
    assert proc.returncode == 0
    assert "readyok" in proc.stdout


def test_missing_nnue_weights_exits_nonzero() -> None:
    """Missing ANCE_NNUE_PATH when ANCE_EVAL=nnue fails fast (D-06)."""
    proc = subprocess.run(
        [sys.executable, "-m", ENGINE_MODULE],
        input="quit\n",
        capture_output=True,
        text=True,
        env=_stripped_env(
            ANCE_EVAL="nnue",
            ANCE_NNUE_PATH="/nonexistent/path/to/net.safetensors",
        ),
        timeout=10,
    )
    assert proc.returncode != 0
    assert "nnue" in proc.stderr.lower() or "weight" in proc.stderr.lower()


def test_symmetric_positions_score_zero() -> None:
    """Color-symmetric positions: exact 0 + STM agreement (D-14)."""
    from ance.eval.nnue.eval import NnueEval

    nnue = NnueEval()
    # Startpos is fully color-symmetric; NNUE has no tempo term → exact 0.
    # King-only (SYMMETRIC_FEN) is also color-symmetric but Phase 4 weights
    # produce a nonzero shared bias on that feature pattern (~-20); both STMs
    # must still agree (perspective invariance).
    assert nnue.evaluate(Position()) == 0
    black_start = chess.Board()
    black_start.turn = chess.BLACK
    assert nnue.evaluate(Position(black_start)) == 0

    king_only = chess.Board(SYMMETRIC_FEN)
    white_cp = nnue.evaluate(Position(king_only))
    king_only.turn = chess.BLACK
    assert nnue.evaluate(Position(king_only)) == white_cp


def test_engine_features_match_training_encoder() -> None:
    """Engine encode_position matches training on 100 random legal FENs."""
    import numpy as np
    from ance.eval.nnue import features as engine_features
    from training.data import features as training_features

    rng = np.random.default_rng(42)
    board = chess.Board()
    fens: list[str] = [board.fen()]
    while len(fens) < 100:
        moves = list(board.legal_moves)
        if not moves:
            board.reset()
            continue
        board.push(moves[int(rng.integers(0, len(moves)))])
        if board.is_game_over():
            board.reset()
            continue
        fens.append(board.fen())

    for fen in fens:
        eng_stm, eng_opp = engine_features.encode_position(fen)
        trn_stm, trn_opp = training_features.encode_position(fen)
        assert np.array_equal(eng_stm, trn_stm), fen
        assert np.array_equal(eng_opp, trn_opp), fen


def test_copied_net_passes_schema_validation() -> None:
    """Copied default net passes load_net shape/arch assertions (D-08)."""
    from nnue_format import io as nnue_io
    from nnue_format import schema

    assert _DEFAULT_NET.is_file()
    arrays, meta = nnue_io.load_net(str(_DEFAULT_NET))
    assert arrays["ft.weight"].shape == (768, 256)
    assert arrays["out.weight"].shape == (512, 1)
    assert meta["arch_id"] == schema.ARCH_ID
    assert meta["feature_set"] == schema.FEATURE_SET


@pytest.mark.torch
@pytest.mark.parametrize("fen", _PARITY_FENS)
def test_torch_numpy_parity_held_out(fen: str) -> None:
    """Torch int cp equals NnueEval int cp on 40 held-out FENs (D-13)."""
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


@pytest.mark.parametrize("fen", _COLOR_MIRROR_FENS)
def test_color_mirror_stm_flip(fen: str) -> None:
    """Color-mirror + STM flip scores match (D-15)."""
    from ance.eval.nnue.eval import NnueEval

    nnue = NnueEval()
    board = chess.Board(fen)
    original = nnue.evaluate(Position(board))
    mirrored = board.mirror()
    mirrored.turn = not board.turn
    assert nnue.evaluate(Position(mirrored)) == original


@pytest.mark.skipif(shutil.which("stockfish") is None, reason="stockfish binary not on PATH")
@pytest.mark.parametrize(
    "fen,expect_positive",
    [(f, True) for f in _SF_WON_FENS] + [(f, False) for f in _SF_LOST_FENS],
)
def test_stockfish_sign_agreement(fen: str, expect_positive: bool) -> None:
    """Stockfish white-relative sign agrees with NNUE STM-relative view (D-16)."""
    from ance.eval.nnue.eval import NnueEval

    board = chess.Board(fen)
    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:
        info = engine.analyse(board, chess.engine.Limit(depth=12))
        sf_white = info["score"].white().score(mate_score=10000)
    assert sf_white is not None

    nnue_cp = NnueEval().evaluate(Position(board))
    # Convert NNUE STM-relative to white-relative for sign compare.
    nnue_white = nnue_cp if board.turn == chess.WHITE else -nnue_cp
    if expect_positive:
        assert sf_white > 0
        assert nnue_white > 0
    else:
        assert sf_white < 0
        assert nnue_white < 0


def test_negamax_never_imports_concrete_nnue_or_handcrafted() -> None:
    """negamax.py non-comment lines omit HandcraftedEval and NnueEval."""
    source = Path("ance/search/negamax.py").read_text()
    non_comment = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "NnueEval" not in non_comment
    assert "HandcraftedEval" not in non_comment


def _non_comment_source(path: Path) -> str:
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    )


def test_search_config_unchanged_by_eval_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-04: search modules ignore concrete evals; gauntlet env differs only by ANCE_EVAL.

    Baseline: search/types.py constants are shared by both builds; eval selection
    is env-only at UCI process launch, so search source must not name NnueEval
    or HandcraftedEval.
    """
    search_modules = (
        Path("ance/search/negamax.py"),
        Path("ance/search/transposition.py"),
        Path("ance/search/ordering.py"),
    )
    for module_path in search_modules:
        non_comment = _non_comment_source(module_path)
        assert "NnueEval" not in non_comment
        assert "HandcraftedEval" not in non_comment

    from ance.tools import gauntlet

    engine_argv = [sys.executable, "-m", "ance"]
    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv, **kwargs: type(
            "E",
            (),
            {
                "quit": lambda self: None,
            },
        )(),
    )
    monkeypatch.setattr(
        gauntlet,
        "play_gauntlet_game",
        lambda *args, **kwargs: {
            "outcome": "draw",
            "result": "1/2-1/2",
            "reason": "halfmove_cap",
            "moves": 0,
            "forfeited_by": None,
            "elapsed_s": 0.0,
        },
    )

    report = gauntlet.run_gauntlet(
        gauntlet.EngineSpec(
            "hc", list(engine_argv), env={"ANCE_EVAL": "handcrafted"}
        ),
        gauntlet.EngineSpec(
            "nnue", list(engine_argv), env={"ANCE_EVAL": "nnue"}
        ),
        [chess.STARTING_FEN],
        n_games=2,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=20,
        output_path=tmp_path / "d04-params.json",
        search_depth=3,
    )
    params = report["parameters"]
    assert params["engine_a"]["argv"] == params["engine_b"]["argv"] == engine_argv
    a_env = dict(params["engine_a"]["env"])
    b_env = dict(params["engine_b"]["env"])
    assert set(a_env) == set(b_env) == {"ANCE_EVAL"}
    assert a_env["ANCE_EVAL"] == "handcrafted"
    assert b_env["ANCE_EVAL"] == "nnue"


@pytest.mark.slow
def test_ten_game_depth2_nnue_vs_hc_smoke_stub() -> None:
    """Optional pre-flight for Plan 05-03 (skipped unless -m slow).

    Manual: run_gauntlet at depth 2, n_games=10 with ANCE_EVAL=nnue vs
    handcrafted. Acceptance depth for TOOL-04 is N=3 (05-RESEARCH); this stub
    documents the smoke only — Plan 05-03 owns the ≥1000-game D-12 gate.
    """
    pytest.skip(
        "Plan 05-03 owns the TOOL-04 evidence run; use depth=3 for acceptance"
    )
