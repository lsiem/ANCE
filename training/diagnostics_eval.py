"""Cheap NNUE sanity checks before overnight gauntlets (Phase 6)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import chess

from ance.board.position import Position
from ance.eval.nnue.eval import NnueEval


@dataclass
class DiagnosticResult:
    name: str
    ok: bool
    detail: str


def _with_net(path: str | None) -> NnueEval:
    if path:
        os.environ["ANCE_NNUE_PATH"] = str(Path(path).resolve())
    return NnueEval()


def check_startpos_near_zero(nnue: NnueEval, tol: int = 50) -> DiagnosticResult:
    score = nnue.evaluate(Position())
    ok = abs(score) <= tol
    return DiagnosticResult("startpos_near_zero", ok, f"cp={score} tol={tol}")


def check_material_signs(nnue: NnueEval) -> DiagnosticResult:
    # White up a rook / queen — STM white ⇒ positive signs.
    # Magnitude ordering (queen > rook) is recorded but not required to pass:
    # weak nets often scramble piece values while still being measurable.
    rook_up = chess.Board("4k3/8/8/8/8/8/8/4KR2 w - - 0 1")
    queen_up = chess.Board("4k3/8/8/8/8/8/8/4KQ2 w - - 0 1")
    rook_cp = nnue.evaluate(Position(rook_up))
    queen_cp = nnue.evaluate(Position(queen_up))
    ok = rook_cp > 0 and queen_cp > 0
    note = ""
    if ok and queen_cp <= rook_cp:
        note = " (warn: queen_cp <= rook_cp)"
    return DiagnosticResult(
        "material_signs",
        ok,
        f"rook_up={rook_cp} queen_up={queen_cp}{note}",
    )


def check_color_flip(nnue: NnueEval, tol: int = 30) -> DiagnosticResult:
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    board = chess.Board(fen)
    original_turn = board.turn
    a = nnue.evaluate(Position(board))
    flipped = board.mirror()
    flipped.turn = not original_turn
    # After color mirror + side-to-move flip, STM-relative score should match.
    b = nnue.evaluate(Position(flipped))
    ok = abs(a - b) <= tol
    return DiagnosticResult("color_flip", ok, f"a={a} b={b} tol={tol}")


def run_diagnostics(net_path: str | None = None) -> list[DiagnosticResult]:
    nnue = _with_net(net_path)
    return [
        check_startpos_near_zero(nnue),
        check_material_signs(nnue),
        check_color_flip(nnue),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANCE NNUE pre-gauntlet diagnostics")
    parser.add_argument(
        "--net",
        type=str,
        default=None,
        help="Path to net.safetensors (default: ANCE_NNUE_PATH / package net)",
    )
    parser.add_argument(
        "--json-out",
        type=str,
        default=None,
        help="Optional path to write JSON results",
    )
    args = parser.parse_args(argv)
    results = run_diagnostics(args.net)
    payload = {"results": [asdict(r) for r in results], "ok": all(r.ok for r in results)}
    print(json.dumps(payload, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
