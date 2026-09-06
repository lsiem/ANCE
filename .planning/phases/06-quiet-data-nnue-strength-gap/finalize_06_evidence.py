#!/usr/bin/env python3
"""Write 06-GAUNTLET-EVIDENCE.json from closer artifacts (resume / interrupt)."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from importlib.machinery import SourceFileLoader  # noqa: E402

from training.diagnostics_eval import run_diagnostics  # noqa: E402

PHASE_DIR = ROOT / ".planning/phases/06-quiet-data-nnue-strength-gap"
ENGINE_NET = ROOT / "ance/eval/nnue/net.safetensors"
PROBE_CKPT = PHASE_DIR / "probe-200" / "probe-checkpoint.json"
GAUNTLET_CKPT = PHASE_DIR / "06-gauntlet-checkpoint.json"
CLOCK_CKPT = PHASE_DIR / "06-gauntlet-clock-checkpoint.json"


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    closer = SourceFileLoader(
        "post_train_close_06",
        str(PHASE_DIR / "post_train_close_06.py"),
    ).load_module()

    diagnostics = run_diagnostics(str(ENGINE_NET))
    probe = _load(PROBE_CKPT)
    depth_report = _load(GAUNTLET_CKPT)
    clock_report = _load(CLOCK_CKPT)
    net_meta: dict = {}
    if ENGINE_NET.is_file():
        from safetensors import safe_open

        with safe_open(ENGINE_NET, framework="numpy") as handle:
            net_meta = dict(handle.metadata() or {})
    closer._write_evidence(
        diagnostics=diagnostics,
        probe=probe,
        depth_report=depth_report,
        clock_report=clock_report,
        corpus_meta={
            "net_source": str(ENGINE_NET),
            "finalized_utc": datetime.now(UTC).isoformat(),
            "note": (
                "200-game depth-3 probe completed; ≥1000 TOOL-04 skipped "
                "because elo_ci_low was not > 0"
            ),
            **net_meta,
        },
    )
    print(f"wrote {closer.EVIDENCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
