---
phase: quick-260718-tpm
plan: 01
subsystem: training-data-pipeline
tags: [nnue, training-data, huggingface, parquet, ingest]
requires: []
provides:
  - "training.data.hf_ingest: row_to_sample / iter_parquet_samples / iter_hf_samples"
  - "run_bounded HF stream (hf_dataset/hf_max_positions/hf_min_depth/hf_min_knodes) with hf_samples.json resume cache"
  - "fresh_n_games=0 path: no stockfish binary required"
affects: [training/run_pipeline.py]
tech-stack:
  added: [huggingface_hub, pyarrow]
  patterns:
    - "lazy heavy-dep imports inside functions (module import stays dependency-light)"
    - "crc32 FEN-bucket pseudo game_ids for split stability"
key-files:
  created:
    - training/data/hf_ingest.py
    - tests/training/test_hf_ingest.py
    - tests/training/test_run_pipeline_hf.py
  modified:
    - training/run_pipeline.py
    - pyproject.toml
decisions:
  - "Pseudo game_ids via zlib.crc32(fen) % n_buckets ('hf-NNNN'), not built-in hash() — hash() is salted per process, which would break resume determinism and split stability"
  - "Stream order lichess -> HF -> fresh so result-bearing lichess rows win first-wins FEN dedup ties (they feed fit_k_from_samples)"
  - "When fresh labeling is skipped, resolved_depth stays None so labeling_command renders 'unknown' — no misleading stockfish command in export metadata"
  - "iter_hf_samples (network wrapper) deliberately untested; all tests offline via plain dicts and tmp parquet files"
metrics:
  duration: "~10 min"
  completed: "2026-07-18"
status: complete
---

# Quick Task 260718-tpm: Hugging Face Lichess Eval Ingest Summary

HF `Lichess/chess-position-evaluations` parquet stream wired into `run_bounded` as a third data source with STM sign correction, quality filtering, crc32 pseudo game_ids, resume caching, and a stockfish-free HF-primary mode.

## Tasks Completed

| Task | Name | Commits | Files |
| ---- | ---- | ------- | ----- |
| 1 | hf_ingest module (row transform, filter, pseudo game ids, parquet streaming) | 9095ba4 (RED), a496e58 (GREEN) | training/data/hf_ingest.py, tests/training/test_hf_ingest.py, pyproject.toml |
| 2 | Wire HF stream into run_bounded, CLI args, skippable fresh labeling | ae4f0f0 (RED), 68751ee (GREEN) | training/run_pipeline.py, tests/training/test_run_pipeline_hf.py |

## What Was Built

- **`training/data/hf_ingest.py`** — torch-free module with lazy `pyarrow`/`huggingface_hub` imports:
  - `row_to_sample`: OR-semantics depth/knodes quality filter; cp used when present, else mate mapped with the exact `_cp_from_label` 100_000 arithmetic (local constant, no circular import); white-relative score negated when FEN side-to-move is black (mirrors `lichess_ingest.extract_samples`); deterministic `zlib.crc32(fen) % n_buckets` pseudo game_id formatted `hf-NNNN`; returns `source="lichess-hf"`, `game_result=None`.
  - `iter_parquet_samples`: `pyarrow.parquet.ParquetFile.iter_batches(batch_size=65_536, columns=[fen, depth, knodes, cp, mate])` streaming with a `max_positions` cap — never materializes a whole shard (24 GB RAM constraint).
  - `iter_hf_samples`: thin network wrapper — enumerates sorted `.parquet` repo files, `hf_hub_download` per shard, stops before downloading shards past the position budget (never pulls the 42 GB dataset wholesale). Deliberately untested.
- **`training/run_pipeline.py`**:
  - `_ingest_hf` mirrors `_ingest_lichess` (deadline + cap), consuming module-global `iter_hf_samples` so tests can monkeypatch it.
  - `run_bounded` gains `hf_dataset=None, hf_max_positions=250_000, hf_min_depth=20, hf_min_knodes=1000`; `hf_samples.json` resume cache + `hf_ingest` manifest event, exactly following the lichess resume pattern; streams appended lichess → HF → fresh.
  - Entire fresh-labeling block (including the `shutil.which("stockfish")` lookup and RuntimeError) is guarded by `if fresh_n_games > 0:`; `resolved_depth` stays `None` when skipped; clear RuntimeError if no stream at all is configured.
  - CLI: `--hf-dataset`, `--hf-max-positions`, `--hf-min-depth`, `--hf-min-knodes`; `--fresh-n-games` help now documents that 0 skips fresh labeling.
- **`pyproject.toml`**: new `[project.optional-dependencies]` group `hf-ingest = ["huggingface_hub", "pyarrow"]`; both installed into the project venv (huggingface_hub 1.24.0, pyarrow 25.0.0).

## Verification

- `tests/training/` full suite: **57 passed** (16 new hf_ingest + 3 new pipeline HF + all pre-existing, no regressions).
- Sign pin: black-to-move cp=150 → −150.0; mate=3 black-to-move → −99_997.0.
- HF-primary end-to-end test runs `run_bounded` with `fresh_n_games=0`, `shutil.which` patched to `None` (no stockfish), monkeypatched `iter_hf_samples` → writes `net.safetensors` and `hf_samples.json`; second run with a raising iterator proves cache reuse.
- `grep hf_samples.json training/run_pipeline.py` → wired (line 273).
- `python -m training.run_pipeline --help` shows all four new flags.
- Lazy-import check: `training.data.hf_ingest` imports cleanly with `pyarrow` blocked from eager import.
- No test touches the network.

## Deviations from Plan

**1. [Rule 3 - Blocking] Used the main checkout's venv via absolute path**
- **Found during:** Task 1 setup
- **Issue:** The execution worktree has no `.venv`; the plan's `.venv/bin/pip` path only exists in the main checkout.
- **Fix:** Ran installs/tests with `/Users/lasse/Development/Projects/ANCE/.venv/bin/python` from the worktree cwd (`pythonpath=["."]` picks up worktree code). No file changes.

**2. [Minor] `_ingest_hf` parameters are keyword-only** (`repo_id, *, max_positions, min_depth, min_knodes, deadline_monotonic`) rather than all-positional — clearer call sites, same behavior.

Otherwise executed exactly as written.

## Known Stubs

None — `iter_hf_samples` is intentionally thin/untested network code per plan, not a stub.

## Threat Flags

None beyond the plan's threat model. T-quick-01/02/SC mitigations applied: untrusted rows get defensive None/short-FEN handling; batch streaming + position cap bound RAM/download; only the two plan-pinned official packages were installed.

## Next Steps

- Resume the scale training run using `--hf-dataset Lichess/chess-position-evaluations --fresh-n-games 0` as the fast path to a large labeled set (pending todo `2026-07-18-scale-train-and-05-03.md`).

## Self-Check: PASSED

All created files present; all four task commits (9095ba4, a496e58, ae4f0f0, 68751ee) exist on the worktree branch; full training suite green (57 passed).
