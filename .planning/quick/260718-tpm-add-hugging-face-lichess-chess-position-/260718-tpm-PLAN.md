---
phase: quick-260718-tpm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - training/data/hf_ingest.py
  - training/run_pipeline.py
  - pyproject.toml
  - tests/training/test_hf_ingest.py
  - tests/training/test_run_pipeline_hf.py
autonomous: true
requirements: [QUICK-HF-INGEST]
must_haves:
  truths:
    - "run_bounded can consume the Hugging Face Lichess/chess-position-evaluations dataset as a third stream alongside lichess_zst and fresh labeling"
    - "HF cp and mate values (white-relative per Lichess docs) are negated when the FEN side-to-move is black, matching lichess_ingest.extract_samples STM convention"
    - "Rows below the depth/knodes quality thresholds are filtered out; thresholds are CLI-configurable"
    - "HF samples get stable pseudo game_ids (deterministic FEN hash buckets) so split_by_game and assert_no_fen_leakage work"
    - "--fresh-n-games 0 skips fresh Stockfish labeling entirely, so the HF stream can be the primary data source without a stockfish binary"
    - "All new tests pass offline — no network access"
  artifacts:
    - "training/data/hf_ingest.py"
    - "tests/training/test_hf_ingest.py"
    - "tests/training/test_run_pipeline_hf.py"
    - "pyproject.toml (hf-ingest optional-dependencies group)"
  key_links:
    - "training/run_pipeline.py imports iter_hf_samples from training.data.hf_ingest and feeds its output into merge_and_dedup"
    - "hf_ingest pseudo game_ids flow through split_by_game / assert_no_fen_leakage unchanged"
---

<objective>
Add a Hugging Face ingest path for pre-labeled NNUE training data: stream the
`Lichess/chess-position-evaluations` Parquet dataset (395M positions, ~42 GB,
CC0-1.0), filter rows by quality thresholds, convert rows to the pipeline's
STM-relative sample dict format, and wire it into `run_bounded` as an
alternative/primary stream alongside the existing `lichess_zst` and
fresh-labeling streams — with offline tests pinning the sign convention.

Purpose: unblock large-scale training without hours of local Stockfish
labeling (current scale run is paused at ~150k/1M fresh labels).
Output: `training/data/hf_ingest.py`, run_pipeline wiring + CLI args, tests.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@training/run_pipeline.py
@training/data/lichess_ingest.py
@training/data/merge.py
@training/data/split.py
@training/data/kfit.py
@tests/training/conftest.py
@tests/training/test_lichess_ingest_sign.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: hf_ingest module — row transform, quality filter, pseudo game ids, shard streaming</name>
  <files>training/data/hf_ingest.py, tests/training/test_hf_ingest.py, pyproject.toml</files>
  <behavior>
    - Test (sign pin, REQUIRED): a row with a black-to-move FEN (second FEN field is "b") and cp=150 produces a sample with cp == -150; the same cp with a white-to-move FEN stays +150. Mirrors tests/training/test_lichess_ingest_sign.py.
    - Test (mate mapping): white-relative mate=3 with white to move maps to cp 99_997.0; mate=3 with black to move maps to -99_997.0; mate=-2 with white to move maps to -99_998.0 (same 100_000 mate_score arithmetic as run_pipeline._cp_from_label).
    - Test (quality filter): with min_depth=20 and min_knodes=1000, a row with depth=25/knodes=10 passes, depth=10/knodes=5000 passes (OR semantics), depth=10/knodes=10 is rejected, and depth=None/knodes=None is rejected.
    - Test (skip row): a row with cp=None and mate=None returns None (skipped); a FEN with fewer than 2 whitespace fields returns None.
    - Test (pseudo game id): same FEN always yields the same game_id across calls (deterministic, NOT the salted built-in hash); game_id has the form "hf-" + zero-padded bucket index; two calls with n_buckets=8 over ~200 distinct FENs produce more than one distinct game_id.
    - Test (parquet streaming, offline): write a small parquet file to tmp_path via pyarrow with columns fen/line/depth/knodes/cp/mate, then iter_parquet_samples yields exactly the filtered+transformed samples with source == "lichess-hf" and game_result is None, and respects a max_positions cap mid-file.
  </behavior>
  <action>
    Install deps into the project venv: `.venv/bin/pip install huggingface_hub pyarrow`.
    Both are top-tier official packages — huggingface_hub is the official Hugging
    Face client (pypi.org/project/huggingface-hub), pyarrow is Apache Arrow
    (pypi.org/project/pyarrow) — and were explicitly named in the approved task
    description. Record them in pyproject.toml under a new
    `[project.optional-dependencies]` group `hf-ingest = ["huggingface_hub", "pyarrow"]`
    (pyproject currently has no dependency lists; do not add a mandatory
    `dependencies` key — the engine itself must stay dependency-light).

    Create `training/data/hf_ingest.py` (torch-free, mirroring lichess_ingest.py
    style: module docstring, `from __future__ import annotations`, typed
    signatures). Keep `pyarrow` and `huggingface_hub` imports LAZY (inside the
    functions that use them) so importing `training.data.hf_ingest` — and
    therefore `training.run_pipeline` — never requires them (same spirit as
    tests/training/test_no_torch_leakage.py).

    Public API:

    1. `row_to_sample(row: dict, *, min_depth: int = 20, min_knodes: int = 1000, n_buckets: int = 1000, mate_score: int = 100_000) -> dict | None`
       Pure transform for one dataset row (keys: fen, line, depth, knodes, cp, mate).
       - Quality filter (OR semantics): keep the row iff (depth is not None and
         depth >= min_depth) or (knodes is not None and knodes >= min_knodes);
         otherwise return None.
       - Compute the white-relative score: use `cp` when not None; else map
         `mate` with the exact arithmetic of run_pipeline._cp_from_label
         (mate>0 -> mate_score - mate; mate<0 -> -mate_score - mate). Do NOT
         import run_pipeline (that would be circular: run_pipeline imports
         training.data.*); define a local _MATE_SCORE = 100_000 constant. If
         both cp and mate are None, return None.
       - STM sign correction: split the FEN on whitespace; if it has fewer than
         2 fields return None (defensive); if field index 1 == "b", NEGATE the
         score. Lichess publishes these evals white-relative; the pipeline's
         sample contract is STM-relative — this mirrors the negation in
         lichess_ingest.extract_samples.
       - Pseudo game_id: the HF dataset has no game ids, but split_by_game
         splits train/val by game_id. Derive a stable bucket:
         `zlib.crc32(fen.encode("utf-8")) % n_buckets`, formatted as
         `f"hf-{bucket:04d}"`. Must NOT use the built-in hash() — it is salted
         per process, which would break resume determinism and split stability.
         Because the bucket is a pure function of the full FEN, identical FENs
         always share a game_id, so assert_no_fen_leakage holds by construction.
         Document this choice in the module docstring.
       - Return `{"fen": row["fen"], "cp": float(score), "game_result": None,
         "game_id": ..., "source": "lichess-hf"}`.

    2. `iter_parquet_samples(path: str, *, min_depth, min_knodes, n_buckets, max_positions: int | None = None) -> Iterator[dict]`
       Open the file with pyarrow.parquet.ParquetFile (lazy import) and iterate
       `iter_batches(batch_size=65_536, columns=["fen", "depth", "knodes", "cp", "mate"])`,
       calling `batch.to_pylist()` and yielding row_to_sample results that are
       not None; stop after max_positions yielded samples. Row-group/batch
       streaming keeps peak RAM small on the 24 GB M4 — never materialize a
       whole shard.

    3. `iter_hf_samples(repo_id: str = "Lichess/chess-position-evaluations", *, max_positions: int, min_depth: int = 20, min_knodes: int = 1000, n_buckets: int = 1000) -> Iterator[dict]`
       Thin network wrapper (deliberately NOT unit-tested): lazily import
       huggingface_hub; enumerate parquet shard filenames with
       `HfApi().list_repo_files(repo_id, repo_type="dataset")` filtered to
       `.parquet` and sorted; for each shard, `hf_hub_download(repo_id=repo_id,
       filename=..., repo_type="dataset")` (HF cache handles reuse), then
       delegate to iter_parquet_samples with the remaining position budget.
       Return as soon as max_positions samples have been yielded so later
       shards are never downloaded — the 42 GB dataset must never be pulled
       wholesale by default.

    Write `tests/training/test_hf_ingest.py` per the behavior list above.
    Put `pytest.importorskip("pyarrow")` at module top (mirrors the torch
    pattern in tests/training/) so the suite still collects cleanly on
    environments without the hf-ingest extras. All tests are offline: they
    exercise row_to_sample on plain dicts and iter_parquet_samples on a tmp
    parquet file written with pyarrow. Do not test iter_hf_samples.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/training/test_hf_ingest.py -q</automated>
  </verify>
  <done>
    training/data/hf_ingest.py exists with row_to_sample / iter_parquet_samples /
    iter_hf_samples; the sign-convention test pins black-to-move negation;
    quality filter, mate mapping, pseudo-game-id determinism, and parquet
    streaming (with cap) are all covered offline; pyproject.toml documents the
    hf-ingest optional-dependencies group; test file passes.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire HF stream into run_bounded, add CLI args, make fresh labeling skippable</name>
  <files>training/run_pipeline.py, tests/training/test_run_pipeline_hf.py</files>
  <behavior>
    - Test (_ingest_hf cap + deadline shape): with run_pipeline.iter_hf_samples monkeypatched to a fake generator of N samples, _ingest_hf returns at most max_positions samples and passes the thresholds through to the iterator.
    - Test (hf-primary end-to-end, torch-marked): run_bounded(tmp_path, lichess_zst=None, fresh_n_games=0, depth=None, max_hours=0.1, hf_dataset="fake/repo", hf_max_positions=60, epochs=1) with iter_hf_samples monkeypatched to yield ~60 samples over real distinct FENs spanning at least 4 distinct game_id buckets, and shutil.which monkeypatched to return None (proving no stockfish binary is required) completes, writes tmp_path/net.safetensors, and tmp_path/hf_samples.json exists with source == "lichess-hf" rows.
    - Test (resume cache): a second run_bounded call in the same out_dir with iter_hf_samples monkeypatched to raise if called proves hf_samples.json is reused, mirroring the lichess_samples.json resume pattern.
  </behavior>
  <action>
    In training/run_pipeline.py:

    1. Import `iter_hf_samples` at module top via
       `from training.data.hf_ingest import iter_hf_samples` (module-top import
       is required so tests can monkeypatch `run_pipeline.iter_hf_samples`;
       hf_ingest keeps its heavy deps lazy, so this adds no import weight).

    2. Add `_ingest_hf(repo_id: str, max_positions: int, min_depth: int, min_knodes: int, deadline_monotonic: float) -> list[dict]`
       mirroring _ingest_lichess: consume iter_hf_samples, break when
       time.monotonic() >= deadline_monotonic or the cap is reached.

    3. Extend run_bounded with keyword params
       `hf_dataset: str | None = None, hf_max_positions: int = 250_000,
       hf_min_depth: int = 20, hf_min_knodes: int = 1000`.
       When hf_dataset is not None, follow the exact lichess_zst resume
       pattern: cache file `out_dir / "hf_samples.json"` — load it if present,
       else call _ingest_hf, save, and
       record_event(event="hf_ingest", n_samples=..., max_positions=...,
       min_depth=..., min_knodes=...). Stream order matters for
       merge_and_dedup's first-wins FEN dedup: append streams in the order
       lichess_zst -> HF -> fresh, so result-bearing lichess rows win ties
       (they feed fit_k_from_samples; HF rows have game_result=None).

    4. Make the fresh stream optional so HF can be the primary source: guard
       the entire fresh-labeling block (fresh_samples load/generate, depth
       benchmark, labeling, streams.append(fresh_samples)) with
       `if fresh_n_games > 0:`. Move the `shutil.which("stockfish")` lookup and
       its RuntimeError inside that guard — no stockfish requirement when fresh
       labeling is skipped. When skipped, resolved_depth stays None (the
       existing labeling_command fallback already renders "unknown"). After
       stream collection, raise RuntimeError with a clear message if streams is
       empty (no lichess_zst, no hf_dataset, fresh_n_games=0). The existing
       n_games >= 2 and empty-split guards stay unchanged; note the HF
       pseudo-game-id bucketing (default 1000 buckets) satisfies them for any
       realistic cap.

    5. CLI: add `--hf-dataset` (str, default None, help naming
       Lichess/chess-position-evaluations), `--hf-max-positions` (int, default
       250000), `--hf-min-depth` (int, default 20), `--hf-min-knodes` (int,
       default 1000); update the `--fresh-n-games` help text to say 0 skips
       fresh Stockfish labeling; thread all four through main() into
       run_bounded.

    Write tests/training/test_run_pipeline_hf.py per the behavior list.
    Top of file: `pytest.importorskip("torch")` (run_pipeline imports
    training.train), matching test_run_pipeline_smoke.py. Build the fake HF
    samples from real distinct FENs by pushing a scripted sequence of legal
    moves from chess.Board() and recording board.fen() after each ply (shard
    encoding parses FENs, so they must be valid); assign game_ids across at
    least 4 distinct "hf-NNNN" buckets so split_by_game has enough games. The
    end-to-end test relies on the K-fit ValueError fallback to _DEFAULT_K
    (all game_result=None) — assert the run completes rather than asserting K.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/training/test_run_pipeline_hf.py tests/training/test_run_pipeline_smoke.py -q</automated>
  </verify>
  <done>
    run_bounded accepts hf_dataset/hf_max_positions/hf_min_depth/hf_min_knodes
    and merges the HF stream in lichess -> HF -> fresh order with hf_samples.json
    resume caching; fresh_n_games=0 skips labeling and the stockfish PATH
    requirement; CLI exposes the four new flags; new tests pass offline and the
    existing pipeline smoke test still passes.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HF Hub download -> local parquet | Third-party dataset bytes enter the training pipeline |
| PyPI install -> venv | New packages (huggingface_hub, pyarrow) enter the toolchain |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-quick-01 | Tampering | iter_hf_samples / dataset rows | low | mitigate | Rows are treated as untrusted data: defensive None/short-FEN handling in row_to_sample; invalid FENs would fail loudly at shard encoding, never execute |
| T-quick-02 | DoS | shard download / RAM | medium | mitigate | max_positions cap stops shard downloads early; pyarrow iter_batches streams row groups instead of loading 42 GB / whole shards into 24 GB RAM |
| T-quick-SC | Tampering | pip installs | high | mitigate | Only two packages, both official and explicitly user-specified: huggingface_hub (Hugging Face) and pyarrow (Apache Arrow); exact canonical PyPI names pinned in the task action; no other installs permitted |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/training/ -q` — full training suite green (new files plus no regressions in ingest/merge/split/pipeline tests).
- `grep -n "hf_samples.json" training/run_pipeline.py` — resume cache wired.
- `.venv/bin/python -m training.run_pipeline --help` — shows --hf-dataset, --hf-max-positions, --hf-min-depth, --hf-min-knodes.
</verification>

<success_criteria>
- HF ingest module converts dataset rows to the pipeline sample dict contract
  with STM-relative cp (black-to-move negation pinned by a test), quality
  filtering, mate mapping consistent with _cp_from_label, and deterministic
  pseudo game ids.
- run_bounded runs HF-primary with no stockfish binary and no lichess_zst when
  --hf-dataset is given and --fresh-n-games is 0.
- No test touches the network; iter_hf_samples is the only network-aware code
  and stays thin/untested.
- New deps recorded in pyproject optional-dependencies and installed in .venv.
</success_criteria>

<output>
Create `.planning/quick/260718-tpm-add-hugging-face-lichess-chess-position-/260718-tpm-SUMMARY.md` when done.
</output>
