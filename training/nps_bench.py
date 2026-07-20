"""Leaf nps comparison: NNUE (accumulator) vs handcrafted under a short search."""

from __future__ import annotations

import argparse
import json
import threading
import time

import chess

from ance.board.position import Position
from ance.eval.handcrafted import HandcraftedEval
from ance.eval.nnue.eval import NnueEval
from ance.search.negamax import search_root


def _bench(evaluator, fen: str, depth: int = 3) -> dict:
    pos = Position(chess.Board(fen))
    stop = threading.Event()
    t0 = time.perf_counter()
    result = search_root(pos, max_depth=depth, evaluator=evaluator, stop_flag=stop)
    elapsed = max(1e-9, time.perf_counter() - t0)
    nodes = int(result.nodes)
    return {
        "nodes": nodes,
        "elapsed_s": elapsed,
        "nps": nodes / elapsed,
        "best_move": result.best_move.uci() if result.best_move else None,
        "score": result.score,
    }


def run_nps_bench(depth: int = 3) -> dict:
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    hc = _bench(HandcraftedEval(), fen, depth=depth)
    nnue = _bench(NnueEval(), fen, depth=depth)
    return {
        "fen": fen,
        "depth": depth,
        "handcrafted": hc,
        "nnue": nnue,
        "nps_ratio_nnue_over_hc": nnue["nps"] / hc["nps"] if hc["nps"] else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NNUE vs handcrafted nps bench")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--json-out", type=str, default=None)
    args = parser.parse_args(argv)
    payload = run_nps_bench(depth=args.depth)
    text = json.dumps(payload, indent=2)
    print(text)
    if args.json_out:
        Path = __import__("pathlib").Path
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
