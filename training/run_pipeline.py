"""Bounded, resumable NNUE training pipeline CLI (D-08).

Per-stage resume uses simple Path.exists() checks under --out-dir (Claude's
Discretion): if an artifact is already present, that stage is skipped.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import chess
import numpy as np

from training.data.hf_ingest import iter_hf_samples
from training.data.kfit import fit_k_from_samples, sigmoid
from training.data.lichess_ingest import extract_samples, iter_games
from training.data.merge import merge_and_dedup
from training.data.shards import build_shard
from training.data.split import assert_no_fen_leakage, split_by_game
from training.export import export_checkpoint
from training.label.position_source import generate_position_set
from training.label.stockfish_labeler import (
    run_and_record_labeling,
    run_depth_benchmark,
)
from training.run_manifest import record_event
from training.train import preflight_mps_gate, run_training

_CANDIDATE_DEPTHS = [10, 14, 18]
_DEFAULT_K = 400.0
_MATE_SCORE = 100_000


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _material_cp(board: chess.Board) -> float:
    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }

    def side_material(color: bool) -> int:
        total = 0
        for piece in board.piece_map().values():
            if piece.color != color or piece.piece_type == chess.KING:
                continue
            total += values[piece.piece_type]
        return total

    cp = float(side_material(chess.WHITE) - side_material(chess.BLACK))
    return cp if board.turn == chess.WHITE else -cp


def _synthetic_samples(n_games: int, seed: int) -> list[dict]:
    raw = generate_position_set(n_games=n_games, seed=seed)
    samples: list[dict] = []
    for sample in raw:
        board = chess.Board(sample["fen"])
        cp = _material_cp(board)
        samples.append(
            {
                **sample,
                "cp": cp,
                "game_result": float(sigmoid(np.array([cp]), _DEFAULT_K)[0]),
                "source": "synthetic",
            }
        )
    return samples


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def _cp_from_label(label: dict, mate_score: int = _MATE_SCORE) -> float | None:
    if label.get("cp") is not None:
        return float(label["cp"])
    mate = label.get("mate")
    if mate is None:
        return None
    mate_n = int(mate)
    if mate_n > 0:
        return float(mate_score - mate_n)
    return float(-mate_score - mate_n)


def _pick_depth(
    rates: dict[int, float],
    n_positions: int,
    remaining_seconds: float,
) -> int:
    """Prefer the deepest candidate that still fits in the labeling budget."""
    labeling_budget = max(60.0, remaining_seconds * 0.7)
    for depth in sorted(rates, reverse=True):
        rate = rates[depth]
        if rate > 0 and (n_positions / rate) <= labeling_budget:
            return depth
    return max(rates, key=rates.get)


def _ingest_lichess(
    zst_path: str,
    sample_cap: int,
    deadline_monotonic: float,
) -> list[dict]:
    samples: list[dict] = []
    for index, game in enumerate(iter_games(zst_path)):
        if time.monotonic() >= deadline_monotonic or len(samples) >= sample_cap:
            break
        samples.extend(extract_samples(game, game_id=f"lichess-{index}"))
        if len(samples) >= sample_cap:
            del samples[sample_cap:]
            break
    return samples


def _ingest_hf(
    repo_id: str,
    *,
    max_positions: int,
    min_depth: int,
    min_knodes: int,
    deadline_monotonic: float,
) -> list[dict]:
    samples: list[dict] = []
    for sample in iter_hf_samples(
        repo_id,
        max_positions=max_positions,
        min_depth=min_depth,
        min_knodes=min_knodes,
    ):
        if time.monotonic() >= deadline_monotonic:
            break
        samples.append(sample)
        if len(samples) >= max_positions:
            break
    return samples


def run_smoke(out_dir: Path, seed: int = 7) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "run_manifest.json"

    device = preflight_mps_gate()
    record_event(str(manifest), event="preflight", device=device, git_sha=_git_sha())

    samples = _synthetic_samples(n_games=8, seed=seed)
    train, val = split_by_game(samples, val_fraction=0.25, seed=seed)
    assert_no_fen_leakage(train, val)

    fitted_k = fit_k_from_samples(train, min_result_rows=10)
    record_event(str(manifest), event="k_fit", k_scale=fitted_k)

    train_shard = out_dir / "train.npz"
    val_shard = out_dir / "val.npz"
    if not train_shard.exists():
        build_shard(train, str(train_shard))
    if not val_shard.exists():
        build_shard(val, str(val_shard))

    result = run_training(
        str(train_shard),
        str(val_shard),
        k=fitted_k,
        epochs=1,
        checkpoint_dir=str(out_dir / "checkpoints"),
    )
    record_event(
        str(manifest),
        event="training_complete",
        val_losses=result["val_losses"],
        device=result["device"],
    )

    net_path = out_dir / "net.safetensors"
    if not net_path.exists():
        export_checkpoint(
            result["model"],
            k_scale=fitted_k,
            path=str(net_path),
            extra_meta={"git_sha": _git_sha(), "mode": "smoke"},
        )

    return {"k": fitted_k, "val_losses": result["val_losses"], "net_path": str(net_path)}


def run_bounded(
    out_dir: Path,
    *,
    lichess_zst: str | None,
    fresh_n_games: int,
    depth: int | None,
    max_hours: float,
    seed: int = 42,
    fresh_target_positions: int | None = None,
    skip_checks: bool = True,
    max_games: int | None = None,
    batch_size: int = 256,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    early_stop_patience: int = 5,
    epochs: int = 50,
    hf_dataset: str | None = None,
    hf_max_positions: int = 250_000,
    hf_min_depth: int = 20,
    hf_min_knodes: int = 1000,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "run_manifest.json"
    deadline = time.monotonic() + max_hours * 3600.0

    device = preflight_mps_gate()
    print(f"device={device}", flush=True)
    record_event(
        str(manifest),
        event="preflight",
        device=device,
        git_sha=_git_sha(),
        fresh_n_games=fresh_n_games,
        fresh_target_positions=fresh_target_positions,
        max_hours=max_hours,
        seed=seed,
        batch_size=batch_size,
    )

    streams: list[list[dict]] = []

    lichess_path = out_dir / "lichess_samples.json"
    if lichess_zst is not None:
        if lichess_path.exists():
            lichess_samples = _load_json(lichess_path)
        else:
            remaining = max(0.0, deadline - time.monotonic())
            # Cheap ingest: cap by remaining wall clock (rough positions/sec floor).
            sample_cap = max(1_000, int(remaining * 20))
            lichess_samples = _ingest_lichess(lichess_zst, sample_cap, deadline)
            _save_json(lichess_path, lichess_samples)
            record_event(
                str(manifest),
                event="lichess_ingest",
                n_samples=len(lichess_samples),
                sample_cap=sample_cap,
            )
        streams.append(lichess_samples)

    # Stream order matters for merge_and_dedup's first-wins FEN dedup:
    # lichess_zst -> HF -> fresh, so result-bearing lichess rows win ties
    # (they feed fit_k_from_samples; HF rows have game_result=None).
    hf_path = out_dir / "hf_samples.json"
    if hf_dataset is not None:
        if hf_path.exists():
            hf_samples = _load_json(hf_path)
        else:
            hf_samples = _ingest_hf(
                hf_dataset,
                max_positions=hf_max_positions,
                min_depth=hf_min_depth,
                min_knodes=hf_min_knodes,
                deadline_monotonic=deadline,
            )
            _save_json(hf_path, hf_samples)
            record_event(
                str(manifest),
                event="hf_ingest",
                n_samples=len(hf_samples),
                max_positions=hf_max_positions,
                min_depth=hf_min_depth,
                min_knodes=hf_min_knodes,
            )
        streams.append(hf_samples)

    stockfish_path: str | None = None
    resolved_depth: int | None = None
    if fresh_n_games > 0:
        stockfish_path = shutil.which("stockfish")
        if stockfish_path is None:
            raise RuntimeError("stockfish binary not found on PATH")

        fresh_path = out_dir / "fresh_samples.json"
        resolved_depth = depth
        if fresh_path.exists():
            fresh_samples = _load_json(fresh_path)
            if resolved_depth is None and manifest.exists():
                for event in _load_json(manifest):
                    if (
                        event.get("event") == "depth_benchmark"
                        and "chosen_depth" in event
                    ):
                        resolved_depth = int(event["chosen_depth"])
                        break
                    if event.get("event") == "fresh_labeling" and "depth" in event:
                        resolved_depth = int(event["depth"])
                        break
        else:
            live_path = out_dir / "training-live.json"

            def _report_generation(done: int, total: int | None) -> None:
                live_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = live_path.with_suffix(live_path.suffix + ".tmp")
                tmp.write_text(
                    json.dumps(
                        {
                            "phase": "generating",
                            "done": done,
                            "total": total,
                            "updated_utc": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            ),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                tmp.replace(live_path)
                print(
                    f"generating positions {done}"
                    + (f"/{total}" if total is not None else ""),
                    flush=True,
                )

            positions = generate_position_set(
                n_games=fresh_n_games,
                seed=seed,
                target_positions=fresh_target_positions,
                skip_checks=skip_checks,
                max_games=max_games,
                progress_callback=_report_generation,
            )
            fens = [row["fen"] for row in positions]
            remaining = max(0.0, deadline - time.monotonic())
            if not fens:
                raise RuntimeError("fresh position set is empty")

            if depth is None:
                rates = run_depth_benchmark(stockfish_path, fens, _CANDIDATE_DEPTHS)
                resolved_depth = _pick_depth(rates, len(fens), remaining)
                record_event(
                    str(manifest),
                    event="depth_benchmark",
                    rates=rates,
                    chosen_depth=resolved_depth,
                    n_positions=len(fens),
                )
            else:
                resolved_depth = depth

            labels = run_and_record_labeling(
                stockfish_path,
                fens,
                resolved_depth,
                str(manifest),
                progress_path=str(out_dir / "fresh_labels_progress.json"),
                live_path=str(out_dir / "training-live.json"),
            )
            fresh_samples = []
            for position, label in zip(positions, labels, strict=True):
                cp = _cp_from_label(label)
                if cp is None:
                    continue
                fresh_samples.append(
                    {
                        "fen": position["fen"],
                        "cp": cp,
                        "game_result": None,
                        "game_id": position["game_id"],
                        "source": "fresh",
                    }
                )
            _save_json(fresh_path, fresh_samples)

        streams.append(fresh_samples)

    if not streams:
        raise RuntimeError(
            "no sample streams configured: provide --lichess-zst, --hf-dataset, "
            "or --fresh-n-games > 0"
        )

    merged_path = out_dir / "merged_samples.json"
    if merged_path.exists():
        merged = _load_json(merged_path)
    else:
        merged = merge_and_dedup(streams)
        _save_json(merged_path, merged)
        record_event(str(manifest), event="merge", n_samples=len(merged))

    if not merged:
        raise RuntimeError("merged sample set is empty")

    n_games = len({sample["game_id"] for sample in merged})
    if n_games < 2:
        raise RuntimeError(
            f"need at least 2 distinct game_id values for train/val split, got {n_games}; "
            "increase --fresh-n-games"
        )

    train, val = split_by_game(merged, val_fraction=0.05, seed=seed)
    if not train or not val:
        # Tiny fresh-only sets can leave a split empty at 5%; widen for viability.
        train, val = split_by_game(merged, val_fraction=0.25, seed=seed)
    if not train or not val:
        raise RuntimeError(
            f"train/val split produced an empty side (train={len(train)}, val={len(val)}); "
            "increase --fresh-n-games"
        )
    assert_no_fen_leakage(train, val)

    try:
        fitted_k = fit_k_from_samples(train)
        k_fallback = False
    except ValueError:
        # Fresh-only labels have no game_result; fall back to the D-04 prior.
        fitted_k = _DEFAULT_K
        k_fallback = True
    record_event(
        str(manifest),
        event="k_fit",
        k_scale=fitted_k,
        fallback=k_fallback,
        seed=seed,
    )

    train_shard = out_dir / "train.npz"
    val_shard = out_dir / "val.npz"
    if not train_shard.exists():
        build_shard(train, str(train_shard))
    if not val_shard.exists():
        build_shard(val, str(val_shard))
    record_event(
        str(manifest),
        event="shards",
        n_train=len(train),
        n_val=len(val),
    )

    sample_fen = train[0]["fen"] if train else None
    result = run_training(
        str(train_shard),
        str(val_shard),
        k=fitted_k,
        epochs=epochs,
        checkpoint_dir=str(out_dir / "checkpoints"),
        deadline_monotonic=deadline,
        batch_size=batch_size,
        lr=lr,
        weight_decay=weight_decay,
        early_stop_patience=early_stop_patience,
        metrics_path=str(out_dir / "metrics.json"),
        sample_fen=sample_fen,
    )
    record_event(
        str(manifest),
        event="training_complete",
        val_losses=result["val_losses"],
        train_losses=result["train_losses"],
        device=result["device"],
        stopped_early=result["stopped_early"],
        global_step=result["global_step"],
        best_epoch=result.get("best_epoch"),
        best_val_loss=result.get("best_val_loss"),
        early_stop_reason=result.get("early_stop_reason"),
        batch_size=result.get("batch_size"),
    )

    labeling_command = (
        f"{stockfish_path} -- chess.engine.SimpleEngine.analyse(depth={resolved_depth})"
        if resolved_depth is not None
        else "unknown"
    )
    net_path = out_dir / "net.safetensors"
    if not net_path.exists():
        export_checkpoint(
            result["model"],
            k_scale=fitted_k,
            path=str(net_path),
            extra_meta={
                "git_sha": _git_sha(),
                "mode": "bounded",
                "labeling_command": labeling_command,
                "n_train": str(len(train)),
                "n_val": str(len(val)),
                "n_merged": str(len(merged)),
                "seed": str(seed),
                "best_epoch": str(result.get("best_epoch")),
                "best_val_loss": str(result.get("best_val_loss")),
                "batch_size": str(batch_size),
            },
        )
        record_event(
            str(manifest),
            event="export",
            path=str(net_path),
            best_epoch=result.get("best_epoch"),
            best_val_loss=result.get("best_val_loss"),
        )

    return {
        "k": fitted_k,
        "val_losses": result["val_losses"],
        "net_path": str(net_path),
        "device": result["device"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANCE offline NNUE training pipeline")
    parser.add_argument("--smoke", action="store_true", help="Tiny synthetic run")
    parser.add_argument(
        "--lichess-zst",
        type=str,
        default=None,
        help="Optional Lichess .pgn.zst dump (skipped when omitted)",
    )
    parser.add_argument(
        "--fresh-n-games",
        type=int,
        default=200,
        help="Random-walk games for fresh Stockfish labeling (0 skips fresh labeling entirely)",
    )
    parser.add_argument(
        "--hf-dataset",
        type=str,
        default=None,
        help=(
            "Hugging Face dataset repo of pre-labeled evals, e.g. "
            "Lichess/chess-position-evaluations (skipped when omitted)"
        ),
    )
    parser.add_argument(
        "--hf-max-positions",
        type=int,
        default=250_000,
        help="Cap on samples ingested from --hf-dataset",
    )
    parser.add_argument(
        "--hf-min-depth",
        type=int,
        default=20,
        help="Keep HF rows with depth >= this (OR --hf-min-knodes)",
    )
    parser.add_argument(
        "--hf-min-knodes",
        type=int,
        default=1000,
        help="Keep HF rows with knodes >= this (OR --hf-min-depth)",
    )
    parser.add_argument(
        "--fresh-target-positions",
        type=int,
        default=None,
        help="Generate/label until this many fresh FENs (e.g. 1000000)",
    )
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--max-hours", type=float, default=10.0)
    parser.add_argument("--out-dir", type=str, default="./training-run-output")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--early-stop-patience", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument(
        "--keep-checks",
        action="store_true",
        help="Do not skip in-check positions when sampling fresh FENs",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=None,
        help="Cap random-walk games when using --fresh-target-positions",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)

    if args.smoke:
        run_smoke(out_dir)
        return 0

    try:
        run_bounded(
            out_dir,
            lichess_zst=args.lichess_zst,
            fresh_n_games=args.fresh_n_games,
            depth=args.depth,
            max_hours=args.max_hours,
            fresh_target_positions=args.fresh_target_positions,
            skip_checks=not args.keep_checks,
            max_games=args.max_games,
            batch_size=args.batch_size,
            lr=args.lr,
            weight_decay=args.weight_decay,
            early_stop_patience=args.early_stop_patience,
            epochs=args.epochs,
            hf_dataset=args.hf_dataset,
            hf_max_positions=args.hf_max_positions,
            hf_min_depth=args.hf_min_depth,
            hf_min_knodes=args.hf_min_knodes,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
