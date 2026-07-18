---
phase: 04-offline-nnue-training-pipeline
plan: 07
status: complete
requirements-completed: [TRN-01, TRN-02, TRN-03, TRN-04, TRN-05]
---

# Phase 04 Plan 07 Summary

**Bounded, resumable pipeline CLI ran the real D-08 training pass on MPS: 13,960 Stockfish-depth-14-labeled positions → 50 epochs → val loss 0.0426 → 0.0169 → approved 790 KB net.safetensors**

## Task Commits

1. **Task 1: CLI orchestrator + smoke test** - `6892973`
2. **Task 2: real bounded run (per-stage resume, deadline stop, NaN-safe WDL loss)** - `ad353ea`
   - Run artifacts (run_manifest.json + net.safetensors) tracked in `0a30b37`; large regenerable data (.npz shards, sample JSONs, checkpoints/) gitignored

## Real Run History (D-08)

| Run | Date | Outcome |
|-----|------|---------|
| #1 | 2026-07-17 | Depth-18 labeling too slow — died overnight before labeling completed |
| #2 | 2026-07-18 | `--depth 14` completed labeling, but training produced all-NaN losses: `wdl_loss` computed `(1-λ)·game_result` with NaN `game_result` on fresh-only labels (`0 × NaN = NaN`). Net deleted. |
| #3 | 2026-07-18 | **Approved.** Bug fixed in `training/train.py` (`torch.where` on target selection so result-less samples never touch `game_result`); resumed from cached labeling/shards and trained clean. |

## Approved Run #3 Metrics

Command: `python -m training.run_pipeline --fresh-n-games 2000 --depth 14 --max-hours 10 --out-dir .planning/phases/04-offline-nnue-training-pipeline/run-output`

- **Labeling:** 13,960 positions, Stockfish depth 14, ~17 min (~13.8 pos/s)
- **Split:** 13,263 train / 697 val (by-game, no FEN leakage)
- **Training:** 50 epochs, 82,900 steps on `mps`, no early stop, no NaN; val loss 0.0426 → 0.016886 (best 0.016805 @ epoch 41)
- **Export:** `run-output/net.safetensors` (790 KB), validated via zero-torch `nnue_format.io.load_net` — all tensors finite; provenance metadata complete (arch 768x2-256-1, seed 42, k_scale 400, git_sha ec45f5b, format_version 1)
- Human checkpoint: developer typed "approved" after inspecting manifest, device banner, val-loss trend, fitted K, and exported weights

## Caveats

- **K=400 is a fallback, not a fit** (`fallback: true`): fresh-only data carries no game outcomes, so the empirical sigmoid fit had nothing to fit. Within the 150–600 plausibility band, but not empirically calibrated.
- **Fresh-only dataset:** 0 Lichess samples — `--lichess-zst` was not supplied, so the bulk-ingest stream (Plan 04-04) remains unexercised against a genuine multi-GB corpus end to end.
- **Mild overfit tail:** after ~epoch 41 val loss plateaus while train loss keeps dropping (→ 0.0023 at epoch 50).
- **Final-epoch export:** the exported net is the epoch-50 model, not the best-val (epoch 41) checkpoint.

## Follow-Up Items (deferred, not implemented)

- Empirical K-fit needs outcome-bearing (Lichess) data — supply a `.pgn.zst` dump on the next run
- Export the best-val checkpoint instead of the final epoch
- Parallel/multi-threaded Stockfish labeling to raise ~13.8 pos/s throughput

## Self-Check: PASSED

- 35 training tests pass at completion; commits `6892973`, `ad353ea`, `0a30b37` verified in log; `run-output/net.safetensors` and `run_manifest.json` exist and are tracked

---
*Completed: 2026-07-18*
