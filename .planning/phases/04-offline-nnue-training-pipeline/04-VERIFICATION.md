---
phase: 04-offline-nnue-training-pipeline
verified: "2026-07-18T09:14:29Z"
status: passed
score: "5/5 roadmap success criteria; 5/5 requirements (TRN-04 engine-startup load deferred to Phase 5)"
behavior_unverified: 0
requirements:
  TRN-01: passed
  TRN-02: passed
  TRN-03: passed
  TRN-04: passed
  TRN-05: passed
deferred:
  - item: "Running engine loads exported weights at UCI startup"
    requirement: TRN-04
    deferred_to: "Phase 5 (NNUE Swap-In & Elo Gauntlet)"
    reason: "Phase 4 success criterion #5 only requires the shared nnue_format loader to validate/roundtrip; engine-side NnueEval load is Phase 5 EVAL-03"
---

# Phase 4: Offline NNUE Training Pipeline Verification

## Goal

An offline PyTorch/MPS pipeline turns Stockfish-labeled positions into a validated, exported `(768→N)×2→1` weights file the engine can load — binding to the engine only through the shared `nnue_format` contract.

**Verified:** 2026-07-18T09:14:29Z
**Status:** `passed`

## Goal Achievement

### Roadmap Success Criteria

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Stockfish labeling produces (FEN → cp) at fixed depth using normalized UCI cp; exact command recorded | PASS | `training/label/stockfish_labeler.py` reads `info["score"].relative` only. Manifest `fresh_labeling` records `/opt/homebrew/bin/stockfish -- chess.engine.SimpleEngine.analyse(depth=14)` for 13,960 positions. Focused labeler tests pass. |
| 2 | Dedup by FEN; train/val split by game; automated no-leakage check | PASS | `merge_and_dedup` + `split_by_game` + `assert_no_fen_leakage` wired in `run_pipeline.py`. Real run: 13,263 / 697. `tests/training/` covers split leakage and merge paths. |
| 3 | `(768→256)×2→1` trains on MPS against sigmoid-WDL with decreasing val loss | PASS | Approved run #3: device `mps`, 50 epochs / 82,900 steps, val loss 0.0426 → 0.016886 (best 0.016805 @ epoch 41). `wdl_loss` uses `torch.sigmoid(·/k)` + NaN-safe `torch.where` for result-less rows. |
| 4 | Preflight checks `mps.is_available()` and float32 CPU-vs-MPS parity | PASS | `preflight_mps_gate()` → `select_device()` + `cpu_vs_mps_parity_check(..., model_factory=NNUE)`. Manifest `preflight` records `device: mps`. MPS gate tests pass. |
| 5 | Export to versioned safetensors; shared zero-torch loader validates arch/feature-set/shapes | PASS | `run-output/net.safetensors` (790 KB) loads via `nnue_format.io.load_net`; metadata `arch_id=768x2-256-1`, `feature_set=board768`, `k_scale=400.0`, `format_version=1`; all tensors finite. Roundtrip tests pass. |

**Roadmap score:** 5/5 fully verified.

### Observable Truths (plan must_haves, aggregated)

| Area | Truths | Status | Notes |
|------|--------|--------|-------|
| 04-01 | MPS gate never crashes; nnue_format roundtrip; no torch in nnue_format; ance ↛ training | ✓ VERIFIED | Prohibitions confirmed by ripgrep; artifacts substantive |
| 04-02 | Forward pass scalar cp; smoke loss decreases; export transposed + loadable | ✓ VERIFIED | Model + train smoke + export tests |
| 04-03 | UCI `score.relative` only; command + depth benchmark recorded | ✓ VERIFIED | Labeler source + manifest provenance |
| 04-04 | Lichess sign correction; skip-and-log malformed; zero FEN leakage | ✓ VERIFIED | Unit tests; real run exercised fresh-only merge path |
| 04-05 | K-fit uses result rows only; 768-index startpos encoding | ✓ VERIFIED | `test_fit_k_from_samples_excludes_eval_only_rows`; features tests |
| 04-06 | Shard shapes; checkpoint `weights_only=True`; E2E smoke | ✓ VERIFIED | `torch.load(..., weights_only=True)`; pipeline smoke tests |
| 04-07 | Bounded resumable CLI + `--smoke`; real D-08 artifacts developer-approved | ✓ VERIFIED | Smoke test; human typed `approved` 2026-07-18 |

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `nnue_format/schema.py`, `nnue_format/io.py` | ✓ EXISTS + SUBSTANTIVE | Zero-torch contract |
| `training/mps_gate.py` | ✓ EXISTS + SUBSTANTIVE | Device select + parity |
| `training/model.py`, `training/train.py`, `training/export.py` | ✓ EXISTS + SUBSTANTIVE | NNUE + WDL + export |
| `training/label/*`, `training/run_manifest.py` | ✓ EXISTS + SUBSTANTIVE | Labeling + provenance |
| `training/data/{lichess_ingest,merge,split,kfit,features,shards}.py` | ✓ EXISTS + SUBSTANTIVE | Full data path |
| `training/run_pipeline.py` | ✓ EXISTS + SUBSTANTIVE | 13.5 KB CLI orchestrator |
| `tests/training/conftest.py` + 35 tests | ✓ EXISTS + SUBSTANTIVE | All green |
| `run-output/net.safetensors` + `run_manifest.json` | ✓ EXISTS + APPROVED | D-08 deliverable |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `run_pipeline` | stages | `preflight_mps_gate` → label/merge/split → `fit_k_from_samples` → shards → `run_training` → `export_checkpoint` | ✓ WIRED |
| `preflight_mps_gate` | device | `mps_gate.select_device` + `cpu_vs_mps_parity_check` | ✓ WIRED |
| `stockfish_labeler` | UCI cp | `info["score"].relative` → manifest `record_event` | ✓ WIRED |
| `export_checkpoint` | shared contract | `nnue_format.io.save_net` | ✓ WIRED |
| `ShardDataset` | train loop | `DataLoader` → `wdl_loss` | ✓ WIRED |
| `fit_k_from_samples` | train | fitted/fallback K into `run_training(..., k=)` | ✓ WIRED |

## Requirement Assessment

| Requirement | Result | Actual evidence |
|---|---|---|
| TRN-01 | PASS | Normalized UCI labeling; depth-14 command in manifest + net metadata |
| TRN-02 | PASS | By-game split 13263/697; leakage assertion in pipeline + tests |
| TRN-03 | PASS | MPS sigmoid-WDL training; approved decreasing val-loss curve |
| TRN-04 | PASS (Phase 4 scope) | Export + zero-torch validate/roundtrip. Engine startup load deferred to Phase 5 |
| TRN-05 | PASS | MPS available on this machine; parity check in preflight; float32 throughout (no AMP) |

## Evidence Integrity

- `run_manifest.json` append-only event log includes run #2 (all-NaN `training_complete`, retained for audit) and run #3 (finite decreasing losses + export).
- Approved net metadata embeds labeling command, `n_train`/`n_val`, seed 42, `k_scale` 400, git SHA `ec45f5b…` (pre-NaN-fix tip of the tree that produced the labels).
- Human checkpoint (Plan 04-07 Task 2): developer typed `approved` after inspecting manifest, device banner, val-loss trend, fitted/fallback K, and exported weights — recorded in `04-07-SUMMARY.md`.
- NaN bug fix (`torch.where` target selection) committed in `ad353ea`.

## Test Results

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/training/ -q` | **35 passed** in 3.28s |

## Human Verification Required

None outstanding. Manual-only items from `04-VALIDATION.md` were satisfied by the Plan 04-07 checkpoint:

1. Overnight-run artifact trustworthiness (TRN-03 / D-08) — approved.
2. MPS engagement vs CPU fallback (TRN-05 / D-09) — manifest records `device: mps`.

## Non-Blocking Concerns / Acknowledged Caveats

- **K=400 fallback** (`fallback: true`): fresh-only labels carry no game outcomes, so empirical K-fit did not run on real data. Within 150–600 band; recalibrate when a Lichess dump is supplied.
- **Lichess bulk stream unexercised end-to-end** on a multi-GB corpus (mechanism covered by unit tests + optional `--lichess-zst` path).
- **Mild overfit tail** after ~epoch 41; export is final-epoch, not best-val (≈0.5% val-loss delta).
- Manifest retains run #2 NaN history beside the approved run #3 — intentional audit trail, not a second active net.

## Deferred Items

| Item | Deferred to | Reason |
|------|-------------|--------|
| Engine loads `net.safetensors` at UCI startup | Phase 5 | Phase 4 binds only through `nnue_format`; `NnueEval` + gauntlet are Phase 5 |

## Gaps Summary

**No gaps found.** Phase goal achieved. Ready to proceed to Phase 5.

## Verdict

**Status: `passed`.** All five roadmap success criteria and all five Phase 4 requirements are verified. The approved D-08 `net.safetensors` is the strength-bearing deliverable Phase 5 will consume. Engine-side load and Elo proof correctly remain Phase 5 work.
