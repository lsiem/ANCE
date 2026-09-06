# Phase 7: NNUE strength recovery - Pattern Map

**Mapped:** 2026-09-06
**Files analyzed:** 11 (8 code files + 2 JSON artifacts + 1 packaged net)
**Analogs found:** 11 / 11

Wave 0 is data-correctness + measure-ladder reuse. Do not invent a new trainer, gauntlet, or dataset adapter. Copy Phase 6 closer / evidence / pytest shape; pad HF FENs in `row_to_sample`; add `--lichess-max-samples` next to `--hf-max-positions`; add `max_kept` next to `hf_ingest.max_positions`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `training/data/hf_ingest.py` | utility | transform | `training/data/hf_ingest.py` (`row_to_sample` FEN parse) + `training/data/quiet_filter.py` (`ply_from_fen`) | exact |
| `training/run_pipeline.py` | controller | batch | `training/run_pipeline.py` (`--hf-max-positions` + `_ingest_lichess` `sample_cap`) | exact |
| `training/data/quiet_filter.py` | utility | transform | `training/data/quiet_filter.py` (`filter_quiet_samples`) + `training/data/hf_ingest.py` (`max_positions` early-stop) | exact |
| `tests/training/test_hf_ingest.py` | test | transform | `tests/training/test_hf_ingest.py` (`TestSkipRow` / `TestSignConvention`) | exact |
| `tests/training/test_quiet_filter.py` | test | transform | `tests/training/test_quiet_filter.py` (`test_enforce_strength_requires_results`) | exact |
| `tests/training/test_run_pipeline_hf.py` | test | batch | `tests/training/test_run_pipeline_hf.py` (`test_ingest_hf_caps_samples_and_forwards_thresholds`) | exact |
| `tests/training/test_phase7_closer_evidence.py` | test | file-I/O | `tests/training/test_phase6_closer_evidence.py` | exact |
| `.planning/phases/07-nnue-strength-recovery/post_train_close_07.py` | utility | batch | `.planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py` | exact |
| `.planning/phases/07-nnue-strength-recovery/07-NET-SIDECAR.json` | config | file-I/O | `training/export.py` (`export_checkpoint` meta) + `06-GAUNTLET-EVIDENCE.json` `corpus` | role-match |
| `.planning/phases/07-nnue-strength-recovery/07-GAUNTLET-EVIDENCE.json` | config | file-I/O | `.planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json` | exact |
| `ance/eval/nnue/net.safetensors` | config | file-I/O | `ance/eval/nnue/net.safetensors` (in-place overwrite via `export_checkpoint`) | exact |

`training/train.py` is **not** modified (D-06/D-07 already implement AdamW, cosine LR, λ schedule, and best-Elo-beats-best-val). Planner only passes CLI flags.

## Pattern Assignments

### `training/data/hf_ingest.py` (utility, transform)

**Analog:** same file `row_to_sample` (lines 41–95) + `quiet_filter.ply_from_fen` field-count gate (lines 49–53)

**Imports pattern** (lines 23–32):

```python
from __future__ import annotations

import time
import zlib
from collections.abc import Iterator

from training.data.cp_clamp import DEFAULT_CP_CLAMP, clamp_training_cp
```

Keep lazy `pyarrow` / `huggingface_hub` imports inside `iter_parquet_samples` / `iter_hf_samples` so `training.run_pipeline` does not require `hf-ingest` extras.

**Core transform — pad 4-field FENs in `row_to_sample` after the existing length check** (insert after lines 77–82; do **not** use `chess.Board(fen).fen()`, which rewrites clocks to `0 1` and still fails `early_ply`):

```python
    fen = row.get("fen")
    if not fen:
        return None
    fields = fen.split()
    if len(fields) < 2:
        return None
    if len(fields) == 4:
        fen = fen + " 0 16"  # fullmove 16 → ply 30 ≥ DEFAULT_MIN_PLY 8
        fields = fen.split()
    if fields[1] == "b":
        score = -score
```

**Why this analog:** `ply_from_fen` already documents the 6-field contract:

```python
# training/data/quiet_filter.py:49-53
    fields = fen.split()
    if len(fields) < 6:
        return 0
```

**Validation / skip pattern** (lines 54–62, 77–82): return `None` for quality misses and short FENs; raise `ValueError` only for `n_buckets <= 0`.

**Error handling:** no try/except in `row_to_sample`. Illegal FENs stay the quiet filter’s job (`is_quiet_fen` → `"illegal"`). Do not import `training.data.quiet_filter` from this module (pipeline already imports both).

**Sample contract must stay** (lines 88–95): `game_result=None`, `source="lichess-hf"`, `game_id=f"hf-{bucket:04d}"`. crc32 the **padded** FEN so identical 4-field rows share an id after normalize.

**Do not change:** `_HF_DEFAULT_REPO`, `_COLUMNS`, OR quality filter, per-shard `hf_hub_download`, `max_positions` early return (lines 132–133, 163–165).

---

### `training/run_pipeline.py` (controller, batch)

**Analog:** same file — `_ingest_lichess` cap (lines 165–178), time-derived `sample_cap` (lines 329–332), `--hf-max-positions` argparse (lines 758–763), `run_bounded` kwargs pass-through (lines 275–276, 894–897)

**Imports pattern** (lines 7–37): keep `from training.data.hf_ingest import iter_hf_samples` and `from training.data.quiet_filter import enforce_corpus_mix, filter_quiet_samples`. Do not import `ance/` training-side extras beyond what already exists.

**Core CLI flag pattern — copy `--hf-max-positions` for `--lichess-max-samples`:**

```python
# training/run_pipeline.py:758-763
    parser.add_argument(
        "--hf-max-positions",
        type=int,
        default=250_000,
        help="Cap on samples ingested from --hf-dataset",
    )
```

Add immediately after `--lichess-zst` (lines 737–742):

```python
    parser.add_argument(
        "--lichess-max-samples",
        type=int,
        default=None,
        help="Cap on samples ingested from --lichess-zst (default: time-derived cap)",
    )
```

**Core ingest cap pattern** (lines 165–178, 329–332):

```python
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

            remaining = max(0.0, deadline - time.monotonic())
            sample_cap = max(1_000, int(remaining * 20))
            lichess_samples = _ingest_lichess(lichess_zst, sample_cap, deadline)
```

When `lichess_max_samples` is set, `sample_cap = min(time_cap, lichess_max_samples)` (or just the explicit cap). Default `None` preserves today’s time-only behavior.

Thread the kwarg through `run_bounded(...)` like `hf_max_positions` (signature lines 275–276, `main` call lines 894–897).

**Quiet-filter wiring** (lines 535–548) — pass `max_kept=120_000` when strength-corpus / Phase 7 CLI runs:

```python
                merged, qstats = filter_quiet_samples(
                    merged,
                    engine=engine,
                    skip_capture_filter=engine is None,
                )
```

**Error handling pattern** (lines 912–914):

```python
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
```

`enforce_corpus_mix` already raises `RuntimeError` (quiet_filter lines 215–221). `--min-has-result-rate 0.15` is an existing flag (lines 839–843) — do not add a second mix guard.

**Do not change:** stream order lichess → HF → fresh (lines 342–344), empty-HF cache skip (lines 365–368), AdamW/LR argparse defaults, `--resume-from-checkpoint` presence (M4 must simply not pass it).

---

### `training/data/quiet_filter.py` (utility, transform)

**Analog:** same file `filter_quiet_samples` (lines 129–185) + `hf_ingest.iter_parquet_samples` `max_positions` early-stop (lines 131–133)

**Imports pattern** (lines 10–22):

```python
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

import chess
import chess.engine

from ance.board.position import Position
from ance.eval.handcrafted import HandcraftedEval
```

`training/` importing `ance/` is allowed. Reverse is forbidden.

**Core early-stop pattern — copy `max_positions` from hf_ingest:**

```python
# training/data/hf_ingest.py:131-133
            yielded += 1
            if max_positions is not None and yielded >= max_positions:
                return
```

Add optional `max_kept: int | None = None` to `filter_quiet_samples`. After `kept.append(sample)`, break when `len(kept) >= max_kept`. Log via existing `QuietFilterStats`; add a `truncated: bool` field or rely on `kept == max_kept` plus pipeline `record_event`.

**Per-source stats (optional RESEARCH pin):** extend `QuietFilterStats` (lines 29–46) with `kept_by_source: dict[str, int]` counted from `sample.get("source")`. Do not change reject reasons (`check` / `early_ply` / `capture_bestmove` / `qsearch` / `illegal`).

**Mix-guard pattern — already parameterized** (lines 188–221). Phase 7 only needs a new unit case at `min_has_result_rate=0.15`; do not change the default `0.50`.

```python
    if strength_corpus and rate < min_has_result_rate:
        raise RuntimeError(
            f"strength corpus requires has_result rate ≥ {min_has_result_rate:.0%}, "
            f"got {rate:.1%} ({n_result}/{len(samples)}). "
            "Provide --lichess-zst with Result+[%eval] games "
            "(e.g. download a month dump from https://database.lichess.org/)."
        )
```

**Do not change:** `DEFAULT_MIN_PLY = 8`, `DEFAULT_QSEARCH_MARGIN = 60`, `DEFAULT_CAPTURE_SKIP_DEPTH = 6`, `ply_from_fen` returning `0` for `< 6` fields (HF pad is the fix, not relaxing ply).

---

### `tests/training/test_hf_ingest.py` (test, transform)

**Analog:** same file — `TestSkipRow.test_short_fen_is_skipped` (lines 70–75) + `TestSignConvention` (lines 27–36)

**Imports / helper pattern** (lines 1–24):

```python
from __future__ import annotations

import zlib

import pytest

pytest.importorskip("pyarrow")

from training.data.hf_ingest import iter_parquet_samples, row_to_sample

def _row(
    fen: str = _WHITE_FEN,
    depth: int | None = 30,
    knodes: int | None = 5,
    cp: int | None = 20,
    mate: int | None = None,
) -> dict:
    return {"fen": fen, "line": "e2e4", "depth": depth, "knodes": knodes, "cp": cp, "mate": mate}
```

**Add a class next to `TestSkipRow`.** Official dataset-card 4-field FEN (RESEARCH Pattern 1):

```python
_HF_CARD_FEN = "2bq1rk1/pr3ppn/1p2p3/7P/2pP1B1P/2P5/PPQ2PB1/R3R1K1 w - -"

class TestFourFieldFenPad:
    def test_official_card_fen_pads_to_six_fields(self) -> None:
        sample = row_to_sample(_row(fen=_HF_CARD_FEN))
        assert sample is not None
        assert len(sample["fen"].split()) == 6
        assert sample["fen"].endswith(" 0 16")

    def test_padded_fen_is_not_early_ply(self) -> None:
        from training.data.quiet_filter import is_quiet_fen, ply_from_fen

        sample = row_to_sample(_row(fen=_HF_CARD_FEN))
        assert ply_from_fen(sample["fen"]) >= 8
        ok, reason = is_quiet_fen(
            sample["fen"], min_ply=8, bestmove_capture_fn=lambda b: False
        )
        assert reason != "early_ply"
```

Keep `test_short_fen_is_skipped` (`"onlyonefield"` → `None`). 6-field fixtures (`_WHITE_FEN`) must still pass unchanged.

---

### `tests/training/test_quiet_filter.py` (test, transform)

**Analog:** same file `test_enforce_strength_requires_results` (lines 96–102) + `test_filter_quiet_samples_stats` (lines 59–74)

**Imports pattern** (lines 1–13):

```python
from training.data.quiet_filter import (
    enforce_corpus_mix,
    filter_quiet_samples,
    is_quiet_fen,
    ply_from_fen,
)
```

**Mix-rate case — copy the raise test, add a pass at 0.15:**

```python
def test_enforce_strength_requires_results() -> None:
    samples = [
        {"fen": "a", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "b", "cp": 0, "source": "hf", "game_result": None},
    ]
    with pytest.raises(RuntimeError, match="has_result"):
        enforce_corpus_mix(samples, strength_corpus=True, min_has_result_rate=0.50)
```

Add `test_enforce_strength_allows_015_when_enough_results` with 15% `game_result` set and `min_has_result_rate=0.15` (no raise). Keep the 0.50 default test.

**`max_kept` case — copy `test_filter_quiet_samples_stats` loop:** build 3 keepable late-ply quiet FENs (or inject `bestmove_capture_fn=lambda b: False` + `min_ply=0` on non-check positions), call `filter_quiet_samples(..., max_kept=2)`, assert `len(kept) == 2`.

---

### `tests/training/test_run_pipeline_hf.py` (test, batch)

**Analog:** same file `test_ingest_hf_caps_samples_and_forwards_thresholds` (lines 47–85) + `test_run_bounded_lichess_wins_fen_dedup_over_hf` (lines 201–238)

**Imports / mark pattern** (lines 1–17):

```python
from __future__ import annotations

import json
import pytest

pytest.importorskip("torch")

from training import run_pipeline

pytestmark = pytest.mark.torch
```

**Cap-forward pattern** — add `test_ingest_lichess_honors_lichess_max_samples` that monkeypatches `iter_games` / `extract_samples` (or calls `_ingest_lichess` with a tiny `sample_cap`) the same way HF tests stub `iter_hf_samples`.

When wiring `run_bounded(..., lichess_max_samples=80000)`, extend the existing `_ingest_lichess` lambda mock (lines 219–221) to capture the `sample_cap` argument:

```python
    monkeypatch.setattr(
        run_pipeline, "_ingest_lichess", lambda *a, **k: list(lichess_samples)
    )
```

Prefer asserting the cap without a full `run_bounded` if torch-marked e2e is too heavy — unit-test `_ingest_lichess` + argparse `main` parse if a lightweight parse helper exists. There is no `parse_args` test today; do not add a new test file — keep additions here.

---

### `tests/training/test_phase7_closer_evidence.py` (test, file-I/O)

**Analog:** `tests/training/test_phase6_closer_evidence.py` (entire file, 97 lines)

**Imports / loader pattern** (lines 1–18):

```python
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from importlib.machinery import SourceFileLoader


def test_write_evidence_schema(tmp_path, monkeypatch) -> None:
    mod_path = Path(
        ".planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py"
    )
    mod = SourceFileLoader("post_train_close_06", str(mod_path)).load_module()
    monkeypatch.setattr(mod, "EVIDENCE", tmp_path / "06-GAUNTLET-EVIDENCE.json")
    monkeypatch.setattr(mod, "CHECKPOINT", tmp_path / "ckpt.json")
```

Copy this file. Point `SourceFileLoader` at `post_train_close_07.py`. Monkeypatch `EVIDENCE`, `CHECKPOINT`, and the new `SIDECAR` path.

**Required new cases (RESEARCH Validation Architecture):**

1. `test_write_evidence_schema` — `schema_version == 1`, keys include `probe_smoke`, `compare_phase6`, `blocked`.
2. `test_shutout_probe_serializes_without_nan` — copy Phase 6 (lines 52–96): `elo` / `elo_ci_low` JSON `null`, no `Infinity`/`NaN`.
3. `test_blocked_without_sidecar` — missing sidecar → `blocked.reason == "phase7_net_not_installed"`, `gauntlet.status == "blocked"`, `gates_failed` contains `D-14` and `TOOL-04`, no gauntlet call (monkeypatch `run_elo_probe` / `run_gauntlet` to raise if invoked).
4. `test_smoke_abort_skips_200` — smoke `wins == 0` or `score_rate == 0.0` or `elo_ci_high < -200` → evidence written, 200-game probe not started.

**`compare_phase6` fixture values** (from analog evidence JSON lines 42–54):

```python
PHASE6_BASELINE = {
    "probe_200_wins": 0,
    "probe_200_losses": 200,
    "probe_200_draws": 0,
    "elo_ci_high": -686.6071411804116,
    "n_merged": "19866",
    "best_elo": "None",
}
```

---

### `.planning/phases/07-nnue-strength-recovery/post_train_close_07.py` (utility, batch)

**Analog:** `.planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py` (entire file)

**Imports / path bootstrap** (lines 7–24):

```python
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from ance.tools import gauntlet  # noqa: E402
from training.diagnostics_eval import run_diagnostics  # noqa: E402
from training.elo_probe import json_safe_number, probe_summary, run_elo_probe  # noqa: E402
```

Copy the script. Rename `PHASE_DIR` to `07-nnue-strength-recovery`, evidence to `07-GAUNTLET-EVIDENCE.json`. Keep:

```python
PROBE_GAMES = 200
D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
BUDGET_SECONDS = 172_800
PROBE_BUDGET_SECONDS = 64_800
```

Add `SMOKE_GAMES = 16`.

**EngineSpec / depth-3 gauntlet pattern** (lines 68–90) — reuse unchanged (`ANCE_EVAL=nnue` vs `handcrafted`, `search_depth=SEARCH_DEPTH`).

**Identity gate — do not copy Phase 6 “use ENGINE_NET if strength-run missing”** (lines 173–178). Phase 6 net is already at `ance/eval/nnue/net.safetensors`. Require `07-NET-SIDECAR.json` with `phase == 7` and `from_scratch is True` before diagnostics. On miss, write blocked evidence and `return` (D-14). Never call `_install_net` from the Phase 6 net; never train.

**Ladder** (copy `main` lines 169–262, insert smoke after diagnostics):

1. sidecar gate → blocked JSON
2. `run_diagnostics(str(ENGINE_NET))` — fail → evidence, stop (lines 180–192)
3. `run_elo_probe(..., n_games=16, out_dir=PHASE_DIR / "probe-smoke")`
4. Abort 200 if `wins == 0` OR `score_rate == 0.0` OR (`elo_ci_high` is not `None` AND `elo_ci_high < -200`)
5. Existing 200-game gate (lines 215–232)
6. `_run_depth_gauntlet(1000)` only if 200 passed
7. Optional clock gauntlet may be omitted (Phase 7 measure budget is smoke/200/1000)

**Evidence writer** — copy `_write_evidence` (lines 117–166). Keep `json.dumps(..., allow_nan=False)`. Add `blocked`, `probe_smoke` (via `probe_summary`), `compare_phase6` (hard-code Phase 6 baseline). On useful-fail (200 better than 0–200 but TOOL-04 unmet) still `gates_failed: ["D-12", "TOOL-04"]`.

**Error handling** (lines 202–214): catch probe exceptions, write evidence, return 2. No second train.

---

### `.planning/phases/07-nnue-strength-recovery/07-NET-SIDECAR.json` (config, file-I/O)

**Analog:** `training/export.py` `export_checkpoint` meta (lines 25–31) + Phase 6 evidence `corpus` keys (`06-GAUNTLET-EVIDENCE.json` lines 5–24)

```python
    meta = {
        "arch_id": schema.ARCH_ID,
        "feature_set": schema.FEATURE_SET,
        "k_scale": str(k_scale),
        "format_version": "1",
        **(extra_meta or {}),
    }
```

M4 train task writes this JSON **next to the committed net**, not inside safetensors. Shape (RESEARCH Evidence Schema):

```json
{
  "phase": 7,
  "from_scratch": true,
  "arch_id": "768x2-256-1",
  "feature_set": "board768",
  "hf_max_positions": 750000,
  "lichess_month": "2013-01",
  "min_has_result_rate": 0.15,
  "n_merged": 0,
  "has_result_rate": 0.0,
  "best_elo": null,
  "best_elo_epoch": null,
  "best_val_loss": null,
  "k_scale": null,
  "installed_utc": null
}
```

Use RFC JSON (`allow_nan=False`). Stringify numeric extras if they also go into safetensors meta (`export_checkpoint` values are `str`). Sidecar itself may use JSON numbers. Closer treats `phase != 7` or `from_scratch != true` as blocked.

---

### `.planning/phases/07-nnue-strength-recovery/07-GAUNTLET-EVIDENCE.json` (config, file-I/O)

**Analog:** `.planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json` (entire file)

Copy `schema_version: 1` keys: `git_commit`, `captured_utc`, `corpus`, `diagnostics`, `probe_200`, `gauntlet`, `clock_gauntlet`, `gates_passed`, `gates_failed`.

Add `blocked`, `probe_smoke`, `compare_phase6` (RESEARCH Evidence Schema). Shutouts stay JSON `null` (Phase 6 `elo` / `elo_ci_low` lines 50–51). Useful-fail still lists `gates_failed: ["D-12", "TOOL-04"]`. Blocked file uses `gauntlet.status: "blocked"` and `gates_failed: ["D-14", "TOOL-04"]`.

Written only by `post_train_close_07.py` (or a tiny finalize helper if 06’s `finalize_06_evidence.py` is reused). Do not hand-author a passing evidence file.

---

### `ance/eval/nnue/net.safetensors` (config, file-I/O)

**Analog:** same path (Phase 6 install) + `training/export.py` `export_checkpoint`

M4 overwrites this tracked file from a **from-scratch** export (`768x2-256-1` / `board768`). Do not `--resume-from-checkpoint` the current 790180-byte Phase 6 net (D-08). Cloud closer reads this path only after sidecar identity passes.

Install copy pattern if strength-run artifact is the train output (Phase 6 closer lines 62–65) — **M4 commit step**, not the cloud closer:

```python
def _install_net(src: Path) -> None:
    ENGINE_NET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, ENGINE_NET)
```

## Shared Patterns

### RFC JSON + shutout nulls
**Source:** `training/elo_probe.py` lines 68–93; Phase 6 closer `_write_evidence` lines 162–164
**Apply to:** `post_train_close_07.py`, both JSON artifacts, Phase 7 evidence tests

```python
def json_safe_number(value):
    """RFC JSON cannot encode NaN/±Inf; shutouts use null + score_rate=0."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value

    EVIDENCE.write_text(
        json.dumps(evidence, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
```

### Depth-3 ANCE_EVAL gauntlet
**Source:** `post_train_close_06.py` lines 68–90; `training/elo_probe.py` lines 33–43
**Apply to:** smoke, 200, 1000 in the Phase 7 closer (not a new runner)

```python
    spec_nnue = gauntlet.EngineSpec(
        "nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}
    )
    spec_hc = gauntlet.EngineSpec(
        "handcrafted", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
    )
```

In-train probes already set `ANCE_NNUE_PATH` (`elo_probe.py` lines 34–37). Closer measure uses the installed in-tree net.

### First-wins merge (lichess then HF)
**Source:** `training/run_pipeline.py` lines 342–344; proven by `test_run_bounded_lichess_wins_fen_dedup_over_hf`
**Apply to:** any pipeline wiring change. Do not reorder streams.

### Pipeline CLI errors
**Source:** `training/run_pipeline.py` lines 912–914; mix `RuntimeError` in `quiet_filter.py` lines 215–221
**Apply to:** new flags / `max_kept` / mix floor. Print `error: {exc}` on stderr; exit 1. Do not swallow.

### Best-Elo beats best-val (do not reimplement)
**Source:** `training/train.py` lines 427–433
**Apply to:** M4 CLI only (`--elo-probe-every 5 --elo-probe-games 12`). No `train.py` edit.

```python
    if best_elo_path.exists():
        load_checkpoint(model, optimizer, str(best_elo_path))
        export_net_path = str(best_elo_net) if best_elo_net.exists() else None
    elif best_path.exists():
        load_checkpoint(model, optimizer, str(best_path))
```

### Layering
**Source:** `tests/training/test_no_torch_leakage.py` (project invariant); ANCE skill
**Apply to:** all files. `ance/` must not import `training/`. Closer script may import both (it lives under `.planning/`, not `ance/`).

### Naming / tests
**Source:** ANCE skill + existing `tests/training/test_*.py`
**Apply to:** snake_case modules, `from __future__ import annotations`, pytest functions/`Test*` classes, `pytest.importorskip` for optional extras, conventional commits (`feat:` / `fix:`).

### Honest fail
**Source:** Phase 6 closer `gates_failed` (lines 159–160) and 06 evidence
**Apply to:** smoke abort, 200 fail, blocked sidecar, TOOL-04 miss. Never retry-until-green or start a second train (D-11).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | Every Wave 0 file has an in-repo analog. `07-NET-SIDECAR.json` is the weakest match (role-match on export meta + evidence corpus); no prior sidecar file exists — copy RESEARCH schema rather than inventing keys. |

## Metadata

**Analog search scope:** `training/`, `training/data/`, `tests/training/`, `ance/tools/`, `ance/eval/nnue/`, `nnue_format/`, `.planning/phases/06-quiet-data-nnue-strength-gap/`
**Files scanned:** 16 tracked analogs (`git ls-files` verified; no `.gsd` mirrors)
**Pattern extraction date:** 2026-09-06
**Project skills applied:** `.claude/skills/ANCE/SKILL.md` (snake_case, named exports, conventional commits, `test_*.py`)
**`.cursor/rules/`:** none
