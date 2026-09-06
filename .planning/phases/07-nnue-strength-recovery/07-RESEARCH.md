# Phase 7: NNUE strength recovery - Research

**Researched:** 2026-09-06
**Domain:** HF-primary quiet-data retrain of `768x2-256-1` / `board768` + Phase 6 measurement ladder (diagnostics → play smoke → 200 → ≥1000 TOOL-04 at depth 3)
**Confidence:** HIGH (in-repo contracts and the HF 4-field FEN / `early_ply` collapse are verified; M4 sitting throughput after the FEN fix is MEDIUM)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Corpus scale and source
- **D-01:** Primary labeled stream is the existing Hugging Face ingest
  `Lichess/chess-position-evaluations` (`training/data/hf_ingest.py`). Do not
  add a new dataset adapter unless planning finds that repo unusable.
- **D-02:** Keep a **modest Lichess PGN fill** (`--lichess-zst`) so λ and
  `fit_k_from_samples` still see `game_result`. HF rows stay `game_result=None`.
  Do not switch to HF-only or drop `--strength-corpus`’s need for a result
  dump.
- **D-03:** **Quiet filter stays on** after merge (checks, capture-bestmoves,
  `|static − qsearch| > 60`). HF depth/knodes quality cuts remain.
- **D-04:** **Raise the HF stream cap** above the default `hf_max_positions=250_000`
  so quiet-filter cannot collapse the set back to ~20k. Exact cap, PGN month,
  and fill size are planner-chosen to fit the M4 sitting.

### Trainer recipe vs data-only
- **D-05:** Architecture stays **`768x2-256-1` / `board768`**. — **Reversibility:**
  one-way — `nnue_format` / EVAL-03 / packaged-net contract already publish this
  arch; a wider or HalfKA net is a different milestone.
- **D-06:** **Data + light recipe tune.** Planning may retune **λ schedule** and
  **fen-skip / epoch count / early-stop**. Leave **AdamW and LR** as in
  `training/train.py` (cosine, current defaults).
- **D-07:** Run **in-train Elo probes**. Install **best-Elo when it beats
  best-val**; do not ship another val-loss min that cannot play (Phase 6
  `best_epoch=18`, `best_elo=None`).
- **D-08:** **Train from scratch** on the new corpus. Do not warm-start
  `ance/eval/nnue/net.safetensors` from Phase 6.

### Acceptance and stop rules
- **D-09:** Keep the Phase 6 ladder: **200-game probe → ≥1000 TOOL-04**, both
  **fixed depth 3**. Same pass bar as Phase 5 D-10–D-12 (Elo > 0 and 95% CI
  low > 0). Do not raise depth to “find” hidden strength.
- **D-10:** Before the 200-game probe: existing **diagnostics** plus a **tiny
  play smoke** (planner picks ~10–20 games at depth 3). If smoke score is 0 or
  the CI is already hopeless, **skip the 200-game run**.
- **D-11:** On smoke or 200-game failure: **stop and fail honestly**. Write
  evidence, do not start 1000 games, do not start a second train in this phase.
- **D-12:** Phase **success** is TOOL-04. A 200-game result clearly better than
  Phase 6 (0–200, CI high −686.6) is a **useful fail** — document Elo/CI vs
  that baseline, still `gates_failed` if TOOL-04 is not met.

### Train and measure venue
- **D-13:** **Train on M4 MPS** (PROJECT hardware). **Measure** (smoke / 200 /
  1000) on the **cloud Linux CPU** gauntlet host so the protocol matches Phase 6
  (Stockfish, 4 cores, ~15GB).
- **D-14:** This cloud agent is **measure-only**. If the trained net is not
  installed in-tree, write a **blocked** evidence file and stop. Do **not**
  start a reduced CPU train as fallback.
- **D-15:** Wall-clock: M4 train sized for **one sitting (~a few hours)**
  including in-train probes. Cloud measure keeps **~18h**, including the
  1000-game run if the 200-game probe passes.
- **D-16:** Land the export by **committing** over
  `ance/eval/nnue/net.safetensors` plus a small metadata/sidecar on the working
  branch (same pattern as Phase 6). Closer reads the in-tree net.

### Claude's Discretion
User answered **You decide** on every follow-up after choosing HF-primary.
Planning/research may pin without another discuss:

- Exact `hf_max_positions`, Lichess dump month, PGN fill size, and whether the
  ≥50% `has_result` floor stays or is lowered slightly to match “modest fill”.
- Exact λ start/end, `random_fen_skipping`, epochs, patience, and in-train
  `elo_probe_every` / `elo_probe_games`.
- Exact smoke game count and abort threshold.
- Sidecar / blocked-evidence JSON shape (prefer the Phase 6
  `06-GAUNTLET-EVIDENCE.json` schema).
- Which M4 CLI flags wrap `--strength-corpus --quiet-filter --hf-dataset …`.

### Folded Todos
None.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed inside strength recovery (corpus, recipe, gates,
venue). HalfKA, self-play, GUI, and compiled port were not reopened.

### Reviewed Todos (not folded)
- `.planning/todos/pending/2026-07-08-phase2-encroissant-validation.md` —
  GUI validation; not TOOL-04.
- `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md` —
  search-depth backlog; Phase 7 stays at depth 3.
- `.planning/todos/pending/2026-07-07-v1_1-gui-local-web-app.md` — v1.1.
- `.planning/todos/pending/2026-07-18-scale-train-and-05-03.md` — prior scale /
  05-03 leftover; Phase 6 already superseded the train story.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **TOOL-04** | The NNUE build shows a measurable Elo gain over the handcrafted build across a ≥1000-game gauntlet reported with error bars. Pass = Elo point estimate > 0 **and** 95% CI low > 0. | Reuse Phase 5 D-10–D-12 + Phase 6 closer ladder at **fixed depth 3**. New closer adds play-smoke + blocked-if-no-Phase-7-net. Evidence schema copies `06-GAUNTLET-EVIDENCE.json`. |
| **Phase 5 D-10** (carried) | Fixed ≥1000 games (no SPRT early-stop). Report Elo + 95% CI; resume via gauntlet checkpoints. | `ance/tools/gauntlet.py` `run_gauntlet` + `SCHEMA_VERSION = 1`. |
| **Phase 5 D-11** (carried) | Fixed `go depth N` both sides. N stays **3**. | `play_gauntlet_game` uses `chess.engine.Limit(depth=search_depth)`. |
| **Phase 5 D-12** (carried) | Elo > 0 and 95% CI lower bound > 0. | `score_rate_to_elo` + Wilson; shutouts serialize as JSON `null` (`json_safe_number`). |
</phase_requirements>

## Summary

Phase 6 did not fail the harness. Diagnostics passed (startpos +13, material polarity, color-flip 12/12) and the 200-game depth-3 probe completed 0–200 (all checkmate, Elo −∞ / JSON `null`, CI high −686.6). The installed net was a val-loss export (`best_epoch=18`, `best_elo=None`) from a quiet 2013-01 corpus with `n_merged=19866`. Phase 7 is a **second strength attempt**: retrain `768x2-256-1` from scratch on an HF-primary labeled stream plus modest Lichess PGN fill, keep the quiet filter, lightly retune λ / fen-skip / epochs, **install best-Elo when probes beat best-val**, then re-run the measurement ladder on the cloud Linux CPU host.

The planning-critical defect is not “HF is too small.” Official `Lichess/chess-position-evaluations` FENs are **4-field** (no halfmove/fullmove). `ply_from_fen` returns `0` when `len(fields) < 6`, and `is_quiet_fen` then rejects `early_ply` (`min_ply=8`). A runtime probe of the dataset-card sample FEN confirmed `quiet4 False early_ply`. That single seam can discard the entire HF stream and leave only Lichess-PGN survivors — exactly the ~20k Phase 6 collapse. **Wave 0 must pad 4-field HF FENs before the quiet filter**, or D-01/D-04 are a no-op.

**Primary recommendation:** Pad HF FENs to 6 fields in `row_to_sample`, raise `--hf-max-positions` to **750000**, keep Lichess **2013-01** as the modest fill, **lower `--min-has-result-rate` to 0.15**, train from scratch on M4 with **in-train probes of 12 games every 5 epochs**, commit `ance/eval/nnue/net.safetensors` plus `07-NET-SIDECAR.json`. Cloud closer is measure-only: diagnostics → **16-game smoke** → 200 → ≥1000; if the sidecar is missing, write blocked evidence and stop (do not re-measure the Phase 6 net).

## Pinned Discretion (planner MUST copy)

These values are locked by research. Do not re-discuss.

| Knob | Pin | Why |
|------|-----|-----|
| `hf_max_positions` | **750000** | Default `250000` [VERIFIED: `training/run_pipeline.py:759-762`]. 3× raise so quiet-filter keep ~10% still yields ~75k HF rows after the FEN-pad fix. Sitting bound: quiet filter **early-stops at 120000 kept**. |
| Lichess dump month | **2013-01** | Same modest dump Phase 6 already used. URL `https://database.lichess.org/standard/lichess_db_standard_rated_2013-01.pgn.zst` (~17.8 MB; sha256 `aa40b3671fa3cf1072eb182892cd90b0e1e003a4a5943492f64b77e7f3fd1635`) [CITED: database.lichess.org/standard/]. Do **not** use a recent tens-of-GB month. |
| PGN fill size | **natural 2013-01 cap + `--lichess-max-samples 80000`** | Pipeline today has no Lichess count cap — only `sample_cap = max(1_000, int(remaining * 20))` [VERIFIED: `training/run_pipeline.py:329-332`]. Add the flag so a dump swap cannot explode the mix. Expected fill after `[%eval]` extract: tens of thousands of result-bearing rows (Phase 6 scale). |
| `min_has_result_rate` | **0.15** | Default `0.50` [VERIFIED: `training/run_pipeline.py:840-843`] is incompatible with HF-primary + modest fill once HF rows survive quiet filter. `fit_k_from_samples` only needs **30** result rows [VERIFIED: `training/data/kfit.py:25`]. Pass `--min-has-result-rate 0.15` with `--strength-corpus`. |
| `start_lambda` / `end_lambda` | **1.0 → 0.75** | Keep the Phase 6 / nnue-pytorch schedule. Intervention is data + net-selection, not a new loss. |
| `random_fen_skipping` | **2** | Light tune from default `3` [VERIFIED: `training/run_pipeline.py:847-851`]. Skip prob = `N/(N+1)` [VERIFIED: `training/data/shards.py:58-72`]. N=2 uses more of a still-bounded post-quiet set. |
| `epochs` | **30** | Default 50; Phase 6 champion was epoch 18. Thirty + patience 6 fits a sitting once probes are small. |
| `early_stop_patience` | **6** | Default 5 [VERIFIED: `training/run_pipeline.py:788`]. Slightly more slack for mixed HF/PGN val noise. |
| `elo_probe_every` / `elo_probe_games` | **5 / 12** | Default `5 / 100` [VERIFIED: `training/run_pipeline.py:859-869`]. 100 games × ~141 s/game (Phase 6 cloud) is ~4 h **per probe** — blows D-15. 12 games × ≤6 probes ≈ one sitting. |
| Smoke games | **16** (8 openings × 2 colors) | D-10 band 10–20. Color-paired like the gauntlet. |
| Smoke abort | **skip 200 if `wins == 0` OR `score_rate == 0.0` OR (`elo_ci_high` is not `None` AND `elo_ci_high < -200`)** | Hopeless CI: Phase 6 shutout CI high was −686.6. A smoke that cannot beat −200 will not pass D-12 at 200. |
| Sidecar / evidence | **Copy `06-GAUNTLET-EVIDENCE.json` `schema_version: 1`; add `probe_smoke`, `blocked`, `compare_phase6`** | See Evidence Schema below. |
| M4 CLI | See **M4 CLI flags** below | Wraps existing `--strength-corpus --quiet-filter --hf-dataset`. |
| AdamW / LR | **do not change** | `AdamW(lr=1e-3, weight_decay=1e-4)`, cosine `eta_min=lr*0.05` [VERIFIED: `training/train.py:166-175`]. D-06. |
| `fresh-n-games` | **0** | HF-primary + PGN fill; no random-walk labeling this phase. |
| `hf_min_depth` / `hf_min_knodes` | **20 / 1000** | Keep defaults (OR semantics) [VERIFIED: `training/data/hf_ingest.py:50-62`]. |

### M4 CLI flags

```bash
python -m training.run_pipeline \
  --strength-corpus \
  --quiet-filter \
  --lichess-zst lichess_db_standard_rated_2013-01.pgn.zst \
  --lichess-max-samples 80000 \
  --hf-dataset Lichess/chess-position-evaluations \
  --hf-max-positions 750000 \
  --hf-min-depth 20 \
  --hf-min-knodes 1000 \
  --fresh-n-games 0 \
  --min-has-result-rate 0.15 \
  --max-fresh-share 0.10 \
  --start-lambda 1.0 \
  --end-lambda 0.75 \
  --random-fen-skipping 2 \
  --epochs 30 \
  --early-stop-patience 6 \
  --batch-size 256 \
  --lr 1e-3 \
  --weight-decay 1e-4 \
  --elo-probe-every 5 \
  --elo-probe-games 12 \
  --max-hours 5 \
  --out-dir .planning/phases/07-nnue-strength-recovery/strength-run
# Do NOT pass --resume-from-checkpoint (D-08 from scratch).
```

`--lichess-max-samples` does not exist today — Wave 0 adds it. Until then the 2013-01 dump is the natural cap.

## Project Constraints (from CLAUDE.md / ANCE skill)

- Python 3.12+, `python-chess`, PyTorch MPS for **M4 training**; this cloud host is CPU-only (`torch 2.14.0+cpu`, `mps_avail False`) and **must not train** (D-14).
- `ance/` must never import `training/` (`tests/training/test_no_torch_leakage.py`).
- Evaluation stays a swappable module; gauntlet builds differ only by `ANCE_EVAL` / `ANCE_NNUE_PATH` (Phase 5 D-01–D-04).
- No HalfKA, hidden ≠ 256, self-play RL, NVIDIA `bullet` / CUDA, compiled port, GUI, or `/gsd-complete-phase 6`.
- snake_case Python; conventional commits; pytest `test_*.py`.
- No `.cursor/rules/` in this repo (none found this session).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HF parquet ingest + 4-field FEN pad | Offline Training — Data (`training/data/hf_ingest.py`) | Pipeline CLI (`training/run_pipeline.py`) | D-01; pad must happen at sample construction so quiet filter sees 6-field FENs |
| Modest Lichess PGN fill + `game_result` | Offline Training — Data (`training/data/lichess_ingest.py`) | `--lichess-zst` / new `--lichess-max-samples` | D-02; only stream with `game_result` |
| Quiet filter + mix guards | Offline Training — Data (`training/data/quiet_filter.py`) | Stockfish capture-bestmove | D-03; add kept-target early-stop for D-15 |
| K-fit + λ WDL train + best-Elo export | Offline Training — Training (`training/train.py`) | `training/elo_probe.py` | D-06/D-07; AdamW/LR unchanged |
| Weights contract | Shared (`nnue_format/schema.py`) | `training/export.py` | D-05; `768x2-256-1` / `board768` |
| Packaged net + sidecar | Engine package (`ance/eval/nnue/net.safetensors`) + phase sidecar | Git commit on working branch | D-16 / D-14 identity check |
| Diagnostics | Offline tool (`training/diagnostics_eval.py`) | — | Pre-smoke polarity gate |
| Smoke / 200 / 1000 measure | Tooling (`ance/tools/gauntlet.py`) | Phase 7 closer (copy of `post_train_close_06.py`) | D-09–D-14; cloud Linux CPU only |
| Elo + Wilson + RFC JSON | Gauntlet aggregate + `elo_probe.json_safe_number` | Evidence JSON | TOOL-04 / D-12; shutouts stay `null` |

## Standard Stack

### Core

| Library | Version (this venv) | Purpose | Why Standard |
|---------|---------------------|---------|--------------|
| Python | 3.12.3 [VERIFIED: `python3 --version`] | Engine + trainer | PROJECT / `requires-python = ">=3.12"` [VERIFIED: `pyproject.toml:5`] |
| PyTorch | 2.14.0+cpu here; M4 uses MPS wheel | Train loop only | Existing; D-13 trains on M4, not this host |
| NumPy | 2.5.2 | Shards / inference | Existing |
| `chess` | 1.11.2 | PGN, FEN, gauntlet arbiter | Existing |
| `safetensors` | 0.8.0 | Net export/load | Existing `nnue_format` |
| `huggingface_hub` | 1.30.0 | `HfApi.list_repo_files` + `hf_hub_download` | Already `hf-ingest` extra [VERIFIED: `pyproject.toml:7-9`] |
| `pyarrow` | 25.0.1 | Parquet batch stream | Already `hf-ingest` extra |
| `zstandard` | 0.25.0 | Lichess `.pgn.zst` | Existing ingest |
| `scipy` | 1.18.1 | `fit_k` | Existing |
| `pytest` | 9.1.1 | Unit / schema tests | Existing |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Stockfish | 16 (`/usr/local/bin/stockfish` on this host) | Quiet capture-bestmove + optional sign checks | M4 train box and cloud closer; do not add a new engine |
| `tqdm` | 4.70.0 | Long ingest/train progress | Existing |
| `nnue_format` | in-repo | `ARCH_ID` / `FEATURE_SET` / shapes | Every export and engine load |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `Lichess/chess-position-evaluations` ingest | New HF adapter / `datasets.load_dataset` | **Forbidden by D-01** unless repo unusable. Repo is usable once FENs are padded. Official usage snippet uses `load_dataset("Lichess/chess-evaluations")` (older name) — do **not** switch; keep `hf_hub_download` per shard [CITED: huggingface.co/docs/huggingface_hub/main/en/guides/download]. |
| 50% `has_result` floor | Keep 0.50 and enlarge PGN fill | Violates “modest fill” + HF-primary. Lower the floor. |
| `elo_probe_games=100` | Keep default | ~4 h/probe on this host (Phase 6 ~141 s/game). Violates D-15. |
| Recent Lichess month | 2024–2026 dump | Tens of GB; not a sitting. |

**Installation:** No new PyPI packages. M4: `pip install -e '.[hf-ingest]'` if extras missing. Cloud measure: existing venv.

**Version verification (this session):** `pip show` / `pip index versions` for `huggingface_hub` 1.30.0, `pyarrow` 25.0.1, `torch` 2.14.0, `numpy` 2.5.2, `chess` 1.11.2, `safetensors` 0.8.0, `pytest` 9.1.1.

## Package Legitimacy Audit

> Phase 7 installs **no new packages**. `gsd-tools query package-legitimacy check --ecosystem pypi` returned **SUS** for every pre-existing package (`too-new` / `unknown-downloads` — registry metadata gap, same as Phase 5). Not actionable. Official sources: huggingface.co, pytorch.org, numpy.org, github.com/niklasf/python-chess, github.com/huggingface/safetensors.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| huggingface_hub | PyPI | mature | — | github.com/huggingface/huggingface_hub | seam SUS / pre-existing extra | Approved — already in `hf-ingest` |
| pyarrow | PyPI | mature | — | arrow.apache.org | seam SUS / pre-existing extra | Approved |
| torch / numpy / chess / safetensors / zstandard / scipy / tqdm / pytest | PyPI | mature | — | upstream official | seam SUS / pre-existing | Approved |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** seam-wide metadata false positive — **do not** insert `checkpoint:human-verify` for these.

## Architecture Patterns

### System Architecture Diagram

```
M4 sitting (train; D-13)                         Cloud Linux CPU (measure-only; D-14)
────────────────────────                         ────────────────────────────────────
Lichess 2013-01 .pgn.zst ──extract_samples──►    07-NET-SIDECAR.json missing?
  game_result set, source=lichess                  │
HF parquet shards (hf_hub_download, cap 750k)      ├─ yes → write blocked evidence, STOP
  row_to_sample: pad 4-field FEN; game_result=None │
  source=lichess-hf                                └─ no  → diagnostics
        │                                                 │ fail → evidence, STOP
        ▼                                                 ▼ pass
 merge first-wins (lichess then HF) [no fresh]        16-game smoke depth 3
        │                                                 │ abort → evidence, STOP
 quiet filter (check / early_ply / capture / qsearch)     ▼
 early-stop at 120k kept                              200-game probe depth 3
        │                                                 │ fail → evidence, STOP
 enforce_corpus_mix (has_result ≥ 0.15)                   ▼
        │                                             ≥1000 TOOL-04 depth 3
 fit_k (≥30 result rows)                                  │
        │                                             07-GAUNTLET-EVIDENCE.json
 run_training AdamW+cosine λ 1.0→0.75                     (compare_phase6 vs 0–200)
 elo_probe every 5 epochs × 12 games
        │
 export best_elo.safetensors if probe Elo beats prior
 else best-val
        │
 commit ance/eval/nnue/net.safetensors
      + 07-NET-SIDECAR.json
```

### Recommended Project Structure

```
training/data/hf_ingest.py          # pad 4-field FEN (Wave 0)
training/run_pipeline.py            # --lichess-max-samples; pass-through pins
training/data/quiet_filter.py       # optional kept-target early-stop
.planning/phases/07-nnue-strength-recovery/
├── strength-run/                   # M4 out-dir (not required on cloud)
├── post_train_close_07.py          # copy 06 closer + smoke + blocked
├── 07-NET-SIDECAR.json             # written on M4 install; closer identity
├── 07-GAUNTLET-EVIDENCE.json       # measure / blocked / useful-fail
└── 07-*-PLAN.md
tests/training/
├── test_hf_ingest.py               # extend: 4-field pad
└── test_phase7_closer_evidence.py  # blocked + smoke abort + schema
ance/eval/nnue/net.safetensors      # overwrite from scratch export (D-08/D-16)
```

### Pattern 1: HF 4-field FEN normalize (required)

**What:** Official dataset FENs omit halfmove/fullmove. Pad before quiet filter.
**When to use:** Every HF sample in `row_to_sample`.
**Example:**

```python
# Source: training/data/hf_ingest.py row_to_sample + quiet_filter.ply_from_fen
# Official card sample (4 fields):
# "2bq1rk1/pr3ppn/1p2p3/7P/2pP1B1P/2P5/PPQ2PB1/R3R1K1 w - -"
fields = fen.split()
if len(fields) == 4:
    fen = fen + " 0 16"  # fullmove 16 → ply 30 ≥ DEFAULT_MIN_PLY 8
# Do not use chess.Board(fen).fen() — that yields "0 1" and still early_ply.
```

### Pattern 2: First-wins merge (lichess then HF)

**What:** `merge_and_dedup` keeps the first FEN. Pipeline stream order is lichess → HF → fresh.
**When to use:** Always. Result-bearing PGN rows win FEN ties so K-fit / λ see `game_result`.

### Pattern 3: Best-Elo export beats best-val

**What:** `run_training` reloads `best_elo.pt` when it exists, else `best.pt`.
**When to use:** `elo_probe_every > 0` (Phase 6 used `0` → `best_elo=None`).

### Pattern 4: Measure-only closer with identity sidecar

**What:** Cloud refuses to play if `07-NET-SIDECAR.json` is absent or `phase != 7`.
**When to use:** D-14. The Phase 6 net is already at `ance/eval/nnue/net.safetensors` (790180 bytes) — file presence is **not** proof of a Phase 7 train.

### Anti-Patterns to Avoid

- **`snapshot_download` the HF repo:** ~42 GB. Existing ingest stops after `max_positions` [VERIFIED: `training/data/hf_ingest.py:147-149`].
- **`--resume-from-checkpoint` on Phase 6 weights:** D-08 from scratch.
- **`elo_probe_games=100` on M4:** sitting killer.
- **Re-measure Phase 6 net** because the file exists.
- **Raise search depth** to hunt Elo (D-09).
- **Second train after smoke/200 fail** (D-11).
- **CPU train on this cloud host** (D-14).
- **Keep `min_has_result_rate=0.50` after FEN pad:** mix guard will raise once HF survives.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HF parquet download | Custom HTTP / `datasets.load_dataset` wholesale | Existing `iter_hf_samples` | Already lazy-caches shards; D-01 |
| PGN zst parse | New parser | `training.data.lichess_ingest` | STM sign + `game_result` already correct |
| Quiet rules | New filter | `quiet_filter.py` + FEN pad | D-03; only pad + early-stop are new |
| Elo / Wilson / shutout JSON | New stats | `gauntlet.score_rate_to_elo`, `wilson_ci`, `json_safe_number` | Phase 6 RFC-JSON already proven |
| Closer ladder | New harness | Copy `post_train_close_06.py` | D-09; add smoke + blocked |
| K-fit | Hand-rolled search | `fit_k_from_samples` | 30-row floor already exists |
| Weights I/O | New format | `nnue_format` + `export_checkpoint` | EVAL-03 contract |

**Key insight:** Phase 7 is a **data-correctness + selection** phase, not a new trainer. The expensive failure mode is measuring the old net or ingesting HF that the quiet filter silently drops.

## Common Pitfalls

### Pitfall 1: HF 4-field FEN → quiet `early_ply` (Phase 6 collapse)

**What goes wrong:** Every official-sample-style HF FEN is rejected; merged set ≈ Lichess-PGN only (~20k).
**Why it happens:** `ply_from_fen` returns 0 when `len(fields) < 6`; `is_quiet_fen` rejects `ply < 8`.
**How to avoid:** Pad in `row_to_sample` to ` 0 16`. Unit-test the dataset-card sample FEN.
**Warning signs:** `quiet_filter` event with `rejected_early_ply` ≈ HF `n_samples`; `n_merged` stuck near 20k; `source=lichess-hf` count near 0 after merge.

### Pitfall 2: 50% `has_result` vs HF-primary

**What goes wrong:** After FEN pad, `--strength-corpus` raises `strength corpus requires has_result rate ≥ 50%`.
**Why it happens:** HF rows are `game_result=None` [VERIFIED: `training/data/hf_ingest.py:89-95`].
**How to avoid:** `--min-has-result-rate 0.15`.
**Warning signs:** Pipeline exit 1 at `enforce_corpus_mix` after a large HF ingest.

### Pitfall 3: In-train 100-game probes blow the sitting

**What goes wrong:** Default `elo_probe_games=100` × several epochs exceeds D-15.
**Why it happens:** Depth-3 Python search was ~141 s/game on this host (Phase 6 notes).
**How to avoid:** `--elo-probe-games 12 --elo-probe-every 5`. Probe failures must not kill training (already `except` in `run_training`).
**Warning signs:** `training-live.json` stuck in `elo_probe_*` for hours.

### Pitfall 4: Cloud closer plays the Phase 6 net

**What goes wrong:** 16 h of 0–200 again; wasted 18 h budget.
**Why it happens:** D-14 “net missing” is true-file-missing; Phase 6 net **is** present (`ance/eval/nnue/net.safetensors`).
**How to avoid:** Require `07-NET-SIDECAR.json` with `phase: 7` and `from_scratch: true`.
**Warning signs:** Sidecar absent; net metadata `n_merged=19866`, `best_elo=None`.

### Pitfall 5: Val-loss export that cannot play

**What goes wrong:** Repeat Phase 6 (`best_elo=None`, epoch 18).
**Why it happens:** `--elo-probe-every 0` or probes never beat `-inf`.
**How to avoid:** Probes on; install `best_elo.safetensors` when present [VERIFIED: `training/train.py:427-433`].
**Warning signs:** Sidecar `best_elo` null after train.

### Pitfall 6: Quiet-filter wall-clock on 750k + Stockfish d6

**What goes wrong:** Capture-bestmove at `DEFAULT_CAPTURE_SKIP_DEPTH = 6` on every FEN exceeds the sitting.
**Why it happens:** Filter loop has **no deadline** [VERIFIED: `training/data/quiet_filter.py:129-185`].
**How to avoid:** Early-stop at 120000 kept; log stats; honor pipeline `deadline`.
**Warning signs:** Hours in quiet filter with `kept` already > 120k.

### Pitfall 7: `snapshot_download` or caching an empty HF ingest

**What goes wrong:** 42 GB pull, or resume poisoned by `[]`.
**How to avoid:** Keep per-shard `hf_hub_download`; do not cache empty ingest [VERIFIED: `training/run_pipeline.py:365-368`].
**Warning signs:** Disk cliff; `hf_samples.json` is `[]`.

## Code Examples

### HF sample contract (verbatim)

```python
# Source: training/data/hf_ingest.py:36-95
_HF_DEFAULT_REPO = "Lichess/chess-position-evaluations"
_COLUMNS = ["fen", "depth", "knodes", "cp", "mate"]
# ...
    return {
        "fen": fen,
        "cp": float(score),
        "game_result": None,
        "game_id": f"hf-{bucket:04d}",
        "source": "lichess-hf",
    }
```

### Quiet ply / early_ply (verbatim)

```python
# Source: training/data/quiet_filter.py:24-26, 49-60, 109-113
DEFAULT_QSEARCH_MARGIN = 60
DEFAULT_MIN_PLY = 8
DEFAULT_CAPTURE_SKIP_DEPTH = 6
# ...
    if len(fields) < 6:
        return 0
# ...
    if ply_from_fen(fen) < min_ply:
        return False, "early_ply"
```

### Strength-corpus mix (verbatim)

```python
# Source: training/data/quiet_filter.py:188-221
    min_has_result_rate: float = 0.50,
    strength_corpus: bool = False,
# ...
    if strength_corpus and rate < min_has_result_rate:
        raise RuntimeError(
            f"strength corpus requires has_result rate ≥ {min_has_result_rate:.0%}, "
```

### nnue_format arch (verbatim)

```python
# Source: nnue_format/schema.py:18-26
ARCH_ID = "768x2-256-1"
FEATURE_SET = "board768"
EXPECTED_SHAPES: dict[str, tuple[int, ...]] = {
    "ft.weight": (768, 256),
    "ft.bias": (256,),
    "out.weight": (512, 1),
    "out.bias": (1,),
}
```

### Gauntlet depth + env (verbatim)

```python
# Source: ance/tools/gauntlet.py:37, 54-61, 269-270, 598-601
SCHEMA_VERSION = 1
DEFAULT_OPENINGS = Path(__file__).with_name("openings.epd")
# ...
    env: dict[str, str] = field(default_factory=dict)
# ...
            limit = chess.engine.Limit(depth=search_depth)
# ...
        engine_a = chess.engine.SimpleEngine.popen_uci(
            spec_a.argv, env={**base_env, **spec_a.env}
        )
```

### Phase 6 closer constants (verbatim)

```python
# Source: .planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py:36-44
PROBE_GAMES = 200
D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
BUDGET_SECONDS = 172_800
PROBE_BUDGET_SECONDS = 64_800
```

### Logistic Elo shutout (verbatim)

```python
# Source: ance/tools/gauntlet.py:97-103
def score_rate_to_elo(p: float) -> float:
    """Logistic Elo from a score rate in [0, 1] (∞ at the endpoints)."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    return -400.0 * math.log10(1.0 / p - 1.0)
```

## Evidence Schema (sidecar + closer)

Copy Phase 6 `schema_version: 1` keys (`git_commit`, `captured_utc`, `corpus`, `diagnostics`, `probe_200`, `gauntlet`, `clock_gauntlet`, `gates_passed`, `gates_failed`). Add:

```json
{
  "schema_version": 1,
  "blocked": null,
  "probe_smoke": {
    "n_games": 16,
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "score_rate": null,
    "wilson_low": null,
    "wilson_high": null,
    "elo": null,
    "elo_ci_low": null,
    "elo_ci_high": null,
    "status": "skipped",
    "elapsed_s": null
  },
  "compare_phase6": {
    "probe_200_wins": 0,
    "probe_200_losses": 200,
    "probe_200_draws": 0,
    "elo_ci_high": -686.6071411804116,
    "n_merged": "19866",
    "best_elo": "None"
  }
}
```

Blocked (net / sidecar missing) — still RFC JSON, `allow_nan=False`:

```json
{
  "schema_version": 1,
  "blocked": {
    "reason": "phase7_net_not_installed",
    "detail": "missing 07-NET-SIDECAR.json or phase!=7; refusing to measure Phase 6 net",
    "engine_net": "ance/eval/nnue/net.safetensors"
  },
  "probe_smoke": null,
  "probe_200": null,
  "gauntlet": {
    "games": null,
    "mode": "fixed_depth",
    "depth": 3,
    "status": "blocked"
  },
  "gates_passed": [],
  "gates_failed": ["D-14", "TOOL-04"]
}
```

`07-NET-SIDECAR.json` (committed with the net):

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

Phase 6 baseline to beat (useful-fail compare), from `06-GAUNTLET-EVIDENCE.json`: W/L/D `0/200/0`, `score_rate` 0.0, `elo`/`elo_ci_low` JSON `null`, `elo_ci_high` −686.6071411804116.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Lichess-PGN primary + HF fill + quiet | HF-primary + modest 2013-01 fill + quiet + FEN pad | Phase 7 | Stops silent HF drop |
| Val-loss export (`elo-probe-every 0`) | Best-Elo when probes run | Phase 6 mechanism; Phase 7 must use it | Avoids “fits val, loses 0–200” |
| 50% `has_result` | 15% with modest fill | Phase 7 discretion | Makes HF-primary legal under `--strength-corpus` |
| 200-game first play | 16-game smoke then 200 | D-10 | Abort hopeless nets in ~40 min not 16 h |

**Deprecated/outdated:**
- Completing Phase 6 while TOOL-04 is open.
- Warm-start from `ance/eval/nnue/net.safetensors`.
- Depth > 3 for acceptance.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | After FEN pad, quiet-filter keep on HF is on the order of 10% (Phase 6 collapse was mostly `early_ply`, not qsearch/capture) | Pinned Discretion / Pitfall 1 | 750k may still collapse; early-stop + logged reject reasons are the mitigation |
| A2 | 12 depth-3 games on M4 finish in minutes, not hours | elo_probe pin | If M4 is ~150 s/game, cut to 8 games or every 10 epochs |
| A3 | 2013-01 `[%eval]` density still yields ≥30 result rows after quiet | K-fit | If not, ingest 2013-02 as a second modest dump (still not a recent GB-class month) |
| A4 | Logistic Elo + Wilson remains the D-12 definition | TOOL-04 | Same as Phases 5–6; do not switch to BayesElo |
| A5 | Official dump listing 17,761,302 bytes / sha256 is current | Lichess month | Re-check `sha256sums.txt` on the M4 before curl |

## Open Questions (RESOLVED)

1. **RESOLVED: Quiet-filter keep rate on padded HF (unknown until M4 ingest)**
   - What we know: 4-field FENs are 100% `early_ply` today; qsearch/capture rates after pad are unmeasured.
   - What's unclear: whether 750k → 120k kept is easy or the filter is still brutal.
   - Recommendation: log `QuietFilterStats` by `source`; if kept HF < 30k after a sitting, fail honestly (D-11) — do not start a second train.
   - **Resolved by:** Plan 07-03 contingency — log `kept_by_source`; if kept HF < 30k after quiet, stop honestly and do not start a second train (D-11).

2. **RESOLVED: Does M4 already have the 2013-01 zst + HF shard cache?**
   - What we know: this cloud checkout has the Phase 6 net, not a `strength-run/` tree (06-NOTES).
   - What's unclear: M4 disk/cache state.
   - Recommendation: planner’s M4 train task starts with dump sha256 check + `hf-ingest` extra check.
   - **Resolved by:** Plan 07-03 contingency — confirm `hf-ingest` extras (`pip install -e '.[hf-ingest]'` if missing) and Lichess 2013-01 dump sha256 `aa40b3671fa3cf1072eb182892cd90b0e1e003a4a5943492f64b77e7f3fd1635` before the sitting.

3. **RESOLVED: In-train probe venue**
   - What we know: `elo_probe` uses the same Python gauntlet (depth 3).
   - What's unclear: M4 s/game.
   - Recommendation: first probe is the calibration; if one probe > 25 min, drop to 8 games for the rest of the run (still D-07).
   - **Resolved by:** Plan 07-03 contingency — if the first in-train probe exceeds 25 min, drop remaining probes to 8 games (still D-07).

## Environment Availability

| Dependency | Required By | Available (this cloud host) | Version | Fallback |
|------------|------------|-------------------------------|---------|----------|
| Python 3.12 venv | all | ✓ | 3.12.3 | — |
| torch | train (M4 only) | ✓ CPU only | 2.14.0+cpu; `mps_avail False` | **Do not train here** (D-14) |
| huggingface_hub + pyarrow | HF ingest (M4) | ✓ | 1.30.0 / 25.0.1 | M4 must have `.[hf-ingest]` |
| Stockfish | quiet capture + optional goldens | ✓ | 16 | skip capture only if absent — **not** on M4 if brew SF exists |
| cutechess-cli | optional runner | ✗ | — | python-chess arbiter (Phase 5 D-09) |
| Phase 6 net in-tree | identity contrast | ✓ | 790180 bytes | Must **not** be measured as Phase 7 |
| `07-NET-SIDECAR.json` | D-14 gate | ✗ | — | Blocked evidence |
| Knowledge graph | research | ✗ | no `.planning/graphs/graph.json` | skipped |
| Context7 / Exa MCP | docs | ✗ this session (quota) | — | Official README + huggingface_hub download guide via WebFetch |

**Missing dependencies with no fallback:**
- Phase 7 trained net + sidecar on this host — **expected**. Closer writes blocked evidence.

**Missing dependencies with fallback:**
- cutechess-cli → arbiter
- Context7 this session → official HF README + in-repo Read

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 [VERIFIED: `pip show`] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| Quick run command | `.venv/bin/python -m pytest tests/training/test_hf_ingest.py tests/training/test_quiet_filter.py tests/training/test_phase6_closer_evidence.py tests/training/test_diagnostics_eval.py tests/training/test_lambda_schedule.py -q -x` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q -m 'not slow'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-04 / D-12 | Evidence JSON schema + shutout `null` | unit | `pytest tests/training/test_phase6_closer_evidence.py -x` | ✅ (06); Wave 0 add `test_phase7_closer_evidence.py` |
| TOOL-04 / D-10 | 16-game smoke abort skips 200 | unit | `pytest tests/training/test_phase7_closer_evidence.py::test_smoke_abort_skips_200 -x` | ❌ Wave 0 |
| TOOL-04 / D-14 | Missing sidecar → blocked JSON, no gauntlet | unit | `pytest tests/training/test_phase7_closer_evidence.py::test_blocked_without_sidecar -x` | ❌ Wave 0 |
| TOOL-04 / D-11 | Fixed depth 3 + `ANCE_EVAL` env | unit | `pytest tests/test_nnue_gauntlet_depth.py -x` | ✅ |
| D-01 / D-03 | 4-field HF FEN pads; not `early_ply` | unit | `pytest tests/training/test_hf_ingest.py -x` | ✅ file; ❌ pad cases |
| D-02 / mix | `--min-has-result-rate 0.15` accepted | unit | `pytest tests/training/test_quiet_filter.py::test_enforce_corpus_mix_* -x` | ✅ file; ❌ 0.15 case |
| D-05 | Export `768x2-256-1` / `board768` | unit | `pytest tests/training/test_nnue_format_roundtrip.py -x` | ✅ |
| D-06 / D-07 | λ interpolate; best-Elo preferred | unit | `pytest tests/training/test_lambda_schedule.py tests/training/test_run_training_smoke.py -x` | ✅ |
| D-08 | No resume-from in M4 command | plan/manual | checklist in train plan | n/a |
| TOOL-04 | ≥1000-game Elo CI | slow e2e / closer | closer script (not pytest `-m slow` overnight) | manual-only — 16 h; justified |

### Sampling Rate

- **Per task commit:** quick run command above
- **Per wave merge:** `pytest tests/ -q -m 'not slow'`
- **Phase gate:** suite green **and** `07-GAUNTLET-EVIDENCE.json` written (pass, useful-fail, or blocked)

### Wave 0 Gaps

- [ ] `training/data/hf_ingest.py` — pad 4-field FENs (` 0 16`); test the official sample FEN
- [ ] `training/run_pipeline.py` — `--lichess-max-samples` (default `None` = today’s time cap)
- [ ] `training/data/quiet_filter.py` — optional `max_kept` early-stop + per-source stats
- [ ] `tests/training/test_phase7_closer_evidence.py` — blocked / smoke abort / `compare_phase6` / RFC JSON
- [ ] `.planning/phases/07-nnue-strength-recovery/post_train_close_07.py` — copy 06 + smoke + sidecar gate
- [ ] Framework install: none — pytest already present

## Security Domain

ASVS **5.0.0** L1 thinking for a **local training/measure CLI** (not a web app). No HIGH findings — do not block planning.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No users / sessions |
| V3 Session Management | no | — |
| V4 Access Control | no | Local operator CLI |
| V5 Input Validation | yes | `chess.Board(fen)` reject illegal; allowlist `ANCE_EVAL`; `nnue_format` shape/`arch_id`; path args are local files (`--lichess-zst`, `--out-dir`, `--net`) — do not interpolate into shell |
| V6 Cryptography | no | Public weights; `torch.load(..., weights_only=True)` already [VERIFIED: `training/train.py:95`] |

### Known Threat Patterns for Python NNUE pipeline

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `--lichess-zst` / `--out-dir` / `ANCE_NNUE_PATH` | Tampering | Open as files only; no `shell=True`; safetensors-only load |
| Untrusted HF/PGN FEN | Tampering | `chess.Board` parse; skip illegal; no `eval` on comments |
| Malicious `.pt` resume | Tampering | D-08 forbids resume; `weights_only=True` if any load remains |
| Whole-repo HF pull | Denial of service | Per-shard download + `max_positions` + deadline |
| Pickle / arbitrary code in weights | Elevation | `nnue_format` numpy safetensors, not pickle |

## Sources

### Primary (HIGH confidence)

- `training/data/hf_ingest.py`, `training/run_pipeline.py`, `training/data/quiet_filter.py`, `training/train.py`, `training/elo_probe.py`, `training/diagnostics_eval.py`, `training/data/kfit.py`, `training/data/lichess_ingest.py`, `training/data/merge.py`, `training/data/shards.py`, `training/export.py`, `nnue_format/schema.py`, `ance/tools/gauntlet.py`
- `.planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py`, `06-GAUNTLET-EVIDENCE.json`, `06-VERIFICATION.md`, `06-06-SUMMARY.md`
- `.planning/phases/07-nnue-strength-recovery/07-CONTEXT.md` D-01–D-16
- Runtime probe (this session): official 4-field sample FEN → `ply_from_fen=0` → `early_ply`

### Secondary (MEDIUM confidence)

- Hugging Face dataset card README (fetched 2026-09-06): CC0-1.0; 394,669,566 positions; 957,860,115 rows; 4-field FEN sample; fields `fen,line,depth,knodes,cp,mate`; last updated 2026-07-08. [CITED: https://huggingface.co/datasets/Lichess/chess-position-evaluations]
- huggingface_hub download guide: `hf_hub_download(..., repo_type="dataset")`; do not `snapshot_download` this repo. [CITED: https://huggingface.co/docs/huggingface_hub/main/en/guides/download]
- official-stockfish/nnue-pytorch wiki: λ 1.0 eval / 0.0 outcome; `--random-fen-skipping 3`; play games not val-loss. [CITED: https://github.com/official-stockfish/nnue-pytorch/wiki/Basic-training-procedure-(train.py)]
- OWASP ASVS 5.0.0 project page (2025-05-30). [CITED: https://owasp.org/www-project-application-security-verification-standard/]
- `gsd-tools query classify-confidence --provider webfetch --verified` → LOW; `--provider websearch --verified` → MEDIUM (seam tiers used as required)

### Tertiary (LOW confidence)

- Lichess 2013-01 listing size 17,761,302 bytes + sha256 from directory / `sha256sums.txt` [CITED: https://database.lichess.org/standard/] — re-check on M4
- Historic 121,332 games for 2013-01 [CITED: web.archive.org snapshot of database.lichess.org]

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — no new packages; versions from this venv
- Architecture: **HIGH** — reuse Phase 6 pipeline + closer; FEN pad is the one required code fix
- Pitfalls: **HIGH** — 4-field/`early_ply` verified by Read + runtime; probe-size and sidecar identity verified against Phase 6 evidence

**Research date:** 2026-09-06
**Valid until:** 2026-10-06 (HF dataset updates monthly; re-check card if ingest schema drifts)
