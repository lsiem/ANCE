#!/usr/bin/env python3
"""Opening-book-biased SF depth-12 train for Plan 05-04 (better FENs than random walk)."""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from ance.tools.gauntlet import DEFAULT_OPENINGS, load_openings  # noqa: E402
from training.data.kfit import fit_k_from_samples  # noqa: E402
from training.data.merge import merge_and_dedup  # noqa: E402
from training.data.shards import build_shard  # noqa: E402
from training.data.split import assert_no_fen_leakage, split_by_game  # noqa: E402
from training.export import export_checkpoint  # noqa: E402
from training.label.stockfish_labeler import (  # noqa: E402
    default_label_workers,
    run_and_record_labeling,
)
from training.run_manifest import record_event  # noqa: E402
from training.train import run_training  # noqa: E402

OUT = Path(".planning/phases/04-offline-nnue-training-pipeline/sf-openings-d12")
TARGET = 150_000
DEPTH = 12
DEFAULT_K = 400.0
MATE_SCORE = 100_000


def _cp_from_label(label: dict) -> float | None:
    if label.get("cp") is not None:
        return float(label["cp"])
    mate = label.get("mate")
    if mate is None:
        return None
    mate_n = int(mate)
    if mate_n > 0:
        return float(MATE_SCORE - mate_n)
    return float(-MATE_SCORE - mate_n)


def generate_opening_biased(target: int, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    openings = load_openings(DEFAULT_OPENINGS)
    samples: list[dict] = []
    seen: set[str] = set()

    def add(board: chess.Board, game_id: str) -> None:
        if board.is_check() or board.is_game_over(claim_draw=True):
            return
        fen = board.fen()
        key = " ".join(fen.split()[:4])
        if key in seen:
            return
        seen.add(key)
        samples.append({"fen": fen, "game_id": game_id})

    for oi, opening in enumerate(openings):
        root = chess.Board(opening)
        gid = f"open-{oi:03d}"
        add(root, gid)
        for walk in range(120):
            b = root.copy()
            for ply in range(rng.randint(0, 30)):
                moves = list(b.legal_moves)
                if not moves or b.is_game_over(claim_draw=True):
                    break
                b.push(rng.choice(moves))
                add(b, f"{gid}-w{walk}")
                if len(samples) >= target:
                    return samples

    # Top up with startpos walks if openings exhausted early.
    while len(samples) < target:
        b = chess.Board()
        gid = f"start-{len(samples):06d}"
        for ply in range(50):
            moves = list(b.legal_moves)
            if not moves:
                break
            b.push(rng.choice(moves))
            if ply >= 2:
                add(b, gid)
            if len(samples) >= target:
                break
    return samples


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "run_manifest.json"
    stockfish = shutil.which("stockfish")
    if not stockfish:
        print("stockfish not on PATH", file=sys.stderr)
        return 1

    pos_path = OUT / "positions.json"
    if pos_path.exists():
        positions = json.loads(pos_path.read_text())
        print(f"resume positions {len(positions)}", flush=True)
    else:
        print(f"generating {TARGET} opening-biased FENs", flush=True)
        positions = generate_opening_biased(TARGET)
        pos_path.write_text(json.dumps(positions))
        print(f"generated {len(positions)}", flush=True)
        record_event(str(manifest), event="positions", n=len(positions))

    fresh_path = OUT / "fresh_samples.json"
    if fresh_path.exists():
        fresh_samples = json.loads(fresh_path.read_text())
        print(f"resume fresh_samples {len(fresh_samples)}", flush=True)
    else:
        fens = [p["fen"] for p in positions]
        workers = default_label_workers()
        print(
            f"labeling {len(fens)} depth={DEPTH} workers={workers}",
            flush=True,
        )
        labels = run_and_record_labeling(
            stockfish,
            fens,
            DEPTH,
            str(manifest),
            progress_path=str(OUT / "fresh_labels_progress.json"),
            live_path=str(OUT / "training-live.json"),
            workers=workers,
            threads=1,
            hash_mb=64,
        )
        fresh_samples = []
        for position, label in zip(positions, labels, strict=True):
            cp = _cp_from_label(label)
            if cp is None:
                continue
            # Soft clip extremes to stabilize WDL targets
            cp = max(-2000.0, min(2000.0, cp))
            fresh_samples.append(
                {
                    "fen": position["fen"],
                    "cp": cp,
                    "game_result": None,
                    "game_id": position["game_id"],
                    "source": "fresh-opening-biased",
                }
            )
        fresh_path.write_text(json.dumps(fresh_samples))
        print(f"labeled usable {len(fresh_samples)}", flush=True)

    merged = merge_and_dedup([fresh_samples])
    (OUT / "merged_samples.json").write_text(json.dumps(merged))
    train, val = split_by_game(merged, val_fraction=0.05, seed=42)
    if not train or not val:
        train, val = split_by_game(merged, val_fraction=0.25, seed=42)
    assert_no_fen_leakage(train, val)
    try:
        fitted_k = fit_k_from_samples(train)
    except ValueError:
        fitted_k = DEFAULT_K
    print(f"k={fitted_k} train={len(train)} val={len(val)}", flush=True)

    train_shard = OUT / "train.npz"
    val_shard = OUT / "val.npz"
    if not train_shard.exists():
        build_shard(train, str(train_shard))
    if not val_shard.exists():
        build_shard(val, str(val_shard))

    deadline = time.monotonic() + 6 * 3600
    result = run_training(
        str(train_shard),
        str(val_shard),
        k=fitted_k,
        epochs=50,
        checkpoint_dir=str(OUT / "checkpoints"),
        deadline_monotonic=deadline,
        batch_size=256,
        lr=1e-3,
        weight_decay=1e-4,
        early_stop_patience=8,
        metrics_path=str(OUT / "metrics.json"),
        sample_fen=train[0]["fen"] if train else None,
    )
    export_checkpoint(
        result["model"],
        k_scale=fitted_k,
        path=str(OUT / "net.safetensors"),
        extra_meta={"mode": "sf-openings-d12", "n_train": str(len(train))},
    )
    print(
        "exported",
        OUT / "net.safetensors",
        "best_epoch",
        result.get("best_epoch"),
        "best_val",
        result.get("best_val_loss"),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
