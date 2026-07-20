"""Lichess bulk PGN ingestion with STM sign correction (D-01, D-05)."""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator

import chess
import chess.pgn
import zstandard

from training.data.cp_clamp import DEFAULT_CP_CLAMP, clamp_training_cp

_RESULT_MAP = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}


def iter_games(zst_path: str) -> Iterator[chess.pgn.Game]:
    dctx = zstandard.ZstdDecompressor()
    with open(zst_path, "rb") as fh, dctx.stream_reader(fh) as reader:
        text_stream = io.TextIOWrapper(reader, encoding="utf-8")
        while True:
            try:
                game = chess.pgn.read_game(text_stream)
            except Exception as exc:
                print(
                    f"skipping malformed game/node: {exc}",
                    file=sys.stderr,
                )
                continue
            if game is None:
                break
            yield game


def extract_samples(game: chess.pgn.Game, game_id: str) -> list[dict]:
    game_result_white = _RESULT_MAP.get(game.headers.get("Result", ""))
    if game_result_white is None:
        return []

    samples: list[dict] = []
    board = game.board()

    for node in game.mainline():
        board.push(node.move)
        try:
            comment_eval = node.eval()
        except Exception as exc:
            print(
                f"skipping malformed game/node: {exc}",
                file=sys.stderr,
            )
            continue

        if comment_eval is None:
            continue

        stm_is_white = board.turn == chess.WHITE
        cp = comment_eval.white().score(mate_score=100000)
        if cp is None:
            continue
        if not stm_is_white:
            cp = -cp
        cp = clamp_training_cp(float(cp), DEFAULT_CP_CLAMP)

        game_result_stm = (
            game_result_white if stm_is_white else (1.0 - game_result_white)
        )
        samples.append(
            {
                "fen": board.fen(),
                "cp": cp,
                "game_result": game_result_stm,
                "game_id": game_id,
                "source": "lichess",
            }
        )

    return samples
