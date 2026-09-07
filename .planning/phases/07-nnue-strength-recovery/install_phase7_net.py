#!/usr/bin/env python3
"""Phase 7 sidecar writer and M4 install helper (D-05, D-16).

D-05 one-way lock (keep-768x2-256-1): ARCH_ID and FEATURE_SET are read from
nnue_format.schema at write time. Do not edit nnue_format/schema.py,
training/model.py, or training/train.py from this helper.

Does not train. Does not execute M4_PIPELINE_ARGV.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nnue_format.schema import ARCH_ID, FEATURE_SET  # noqa: E402

PHASE_DIR = ROOT / ".planning/phases/07-nnue-strength-recovery"
ENGINE_NET = ROOT / "ance/eval/nnue/net.safetensors"
SIDECAR_PATH = PHASE_DIR / "07-NET-SIDECAR.json"

REQUIRED_SIDECAR_KEYS = (
    "phase",
    "from_scratch",
    "arch_id",
    "feature_set",
    "hf_max_positions",
    "lichess_month",
    "min_has_result_rate",
    "n_merged",
    "has_result_rate",
    "best_elo",
    "best_elo_epoch",
    "best_val_loss",
    "k_scale",
    "installed_utc",
)

# Exact M4 CLI from 07-RESEARCH.md. Do not execute on this CPU host (D-14).
M4_PIPELINE_ARGV: tuple[str, ...] = (
    "python",
    "-m",
    "training.run_pipeline",
    "--strength-corpus",
    "--quiet-filter",
    "--lichess-zst",
    "lichess_db_standard_rated_2013-01.pgn.zst",
    "--lichess-max-samples",
    "80000",
    "--hf-dataset",
    "Lichess/chess-position-evaluations",
    "--hf-max-positions",
    "750000",
    "--hf-min-depth",
    "20",
    "--hf-min-knodes",
    "1000",
    "--fresh-n-games",
    "0",
    "--min-has-result-rate",
    "0.15",
    "--max-fresh-share",
    "0.10",
    "--start-lambda",
    "1.0",
    "--end-lambda",
    "0.75",
    "--random-fen-skipping",
    "2",
    "--epochs",
    "30",
    "--early-stop-patience",
    "6",
    "--batch-size",
    "256",
    "--lr",
    "1e-3",
    "--weight-decay",
    "1e-4",
    "--elo-probe-every",
    "5",
    "--elo-probe-games",
    "12",
    "--max-hours",
    "5",
    "--out-dir",
    ".planning/phases/07-nnue-strength-recovery/strength-run",
)


def json_safe_number(value: object) -> object:
    """RFC JSON cannot encode NaN/±Inf; sidecar uses null."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sidecar_identity_payload(data: dict) -> bool:
    """True when payload is Phase 7 from-scratch (int 7 or \"7\")."""
    if not isinstance(data, dict):
        return False
    phase = data.get("phase")
    phase_ok = phase == 7 or phase == "7"
    return phase_ok and data.get("from_scratch") is True


def write_sidecar(meta: dict) -> None:
    """Merge RESEARCH keys, lock D-05 arch from schema, dump RFC JSON."""
    payload: dict[str, object] = {
        "phase": 7,
        "from_scratch": True,
        "arch_id": ARCH_ID,
        "feature_set": FEATURE_SET,
        "hf_max_positions": 750000,
        "lichess_month": "2013-01",
        "min_has_result_rate": 0.15,
        "n_merged": 0,
        "has_result_rate": 0.0,
        "best_elo": None,
        "best_elo_epoch": None,
        "best_val_loss": None,
        "k_scale": None,
        "installed_utc": None,
    }
    if meta:
        payload.update(meta)
    payload["phase"] = 7
    payload["from_scratch"] = True
    payload["arch_id"] = ARCH_ID
    payload["feature_set"] = FEATURE_SET
    payload["hf_max_positions"] = 750000
    payload["lichess_month"] = "2013-01"
    payload["min_has_result_rate"] = 0.15
    payload = {key: json_safe_number(value) for key, value in payload.items()}
    SIDECAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    SIDECAR_PATH.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def install_export(src: Path) -> None:
    """Copy a from-scratch export onto ENGINE_NET (M4 commit step, not closer)."""
    ENGINE_NET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, ENGINE_NET)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install Phase 7 export and write 07-NET-SIDECAR.json (M4 sitting)."
    )
    parser.add_argument(
        "--src",
        type=Path,
        help="Exported safetensors copied onto ance/eval/nnue/net.safetensors",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        help="JSON object merged into the sidecar (n_merged, best_elo, …)",
    )
    args = parser.parse_args(argv)
    if args.src is not None:
        install_export(args.src)
    meta: dict = {}
    if args.meta is not None:
        loaded = json.loads(args.meta.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            print("error: --meta must be a JSON object", file=sys.stderr)
            return 1
        meta = loaded
    write_sidecar(meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
