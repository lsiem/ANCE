# Phase 4: Offline NNUE Training Pipeline - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

An **offline** PyTorch/MPS pipeline that turns Stockfish-labeled chess positions
into a validated, exported `(768→N)×2→1` NNUE weights file the engine can load.
It binds to the engine **only** through the shared `nnue_format` weights contract
(arch id / feature-set id / shapes), never through search or eval internals.

Delivers TRN-01…TRN-05:
1. Labeling pipeline → (FEN → cp) samples at fixed depth/nodes, normalized UCI cp, exact command recorded.
2. Deduplicated dataset, train/val split **by game** (not position) with an automated no-FEN-overlap check.
3. `(768→256)×2→1` trains in PyTorch on MPS against a sigmoid-scaled win-probability target, decreasing trustworthy val loss.
4. First task verifies `torch.backends.mps.is_available()` + float32 CPU-vs-MPS numeric sanity check before the real run.
5. Trained weights export to a plain versioned format the shared loader validates and roundtrips with **zero torch dependency**.

Out of scope (own phases): the numpy `NnueEval` swap-in, parity/perspective tests,
and the Elo gauntlet all belong to **Phase 5**. Incremental accumulator (make/unmake
hooks) is a later optimization, not this phase.
</domain>

<decisions>
## Implementation Decisions

### Data source & labeling
- **D-01:** **Hybrid position/label source.** Bootstrap bulk volume from existing
  Lichess `[%eval]` tags (SF-NNUE @ ~40 Mnodes, ~6% of games in the open-database
  `.pgn.zst` dumps), then top up with a **fresh Stockfish labeling pass** over a
  targeted position set for controlled depth/coverage. The two streams merge into
  one deduplicated dataset.
- **D-02:** The fresh-labeling pass MUST record the **exact Stockfish UCI command**
  (fixed depth/nodes) and use **normalized UCI cp** output — never internal eval
  (TRN-01). Planning/research must pin the depth-or-nodes value.
- **D-03:** Dedup by FEN; split **by game** so no FEN leaks across train/val, with an
  automated assertion that the split is disjoint (TRN-02). Lichess-sourced samples
  carry their originating game id so the by-game split applies to them too.

### Training signal & scaling
- **D-04:** Target = **sigmoid-scaled win probability**. The scaling constant **K is
  fit empirically** — choose K minimizing the fit between `sigmoid(cp/K)` and the
  observed game result over the dataset, then **lock and record the fitted K**. This
  resolves the standing STATE blocker (previously "~360–400 must be pinned").
- **D-05:** Where a real game **WDL outcome** is available (Lichess games), it is the
  ground-truth result used in the K fit; cp→sigmoid is the target where only an eval
  exists.

### Net architecture sizing
- **D-06:** **Hidden width N = 256** → `(768→256)×2→1` (~393k feature-transformer
  params). Fixed for this milestone. (Bigger/king-bucketed nets deferred to cloud
  scale-up per PROJECT.md.)

### Export format
- **D-07:** Export via **safetensors** with a JSON header carrying `arch_id`,
  `feature_set_id`, and tensor shapes. The engine-side loader in `nnue_format/`
  validates these and roundtrips with **zero torch dependency** (numpy-only read).

### Compute ambition & bound
- **D-08:** Ambition is **max strength within a bounded M4 run** — NOT the
  "modest first net" default. Planning sizes dataset + epochs to a **fixed
  wall-clock cap (~8–12h, an overnight run)** on the M4, pushing strength as far as
  that budget allows while keeping the run finite and reproducible. This is the
  agreed reconciliation with PROJECT.md's "heavy runs deferred to cloud" — the
  cloud/NVIDIA path remains the route for anything beyond this bounded run.

### MPS safety (locked direction, first task)
- **D-09:** The **very first** training-harness task is an MPS gate:
  `torch.backends.mps.is_available()` smoke test + a float32 CPU-vs-MPS numeric
  parity check on one forward/backward step (TRN-05). CPU training is an accepted
  fallback for this tiny net if MPS is unavailable/regressed on the target macOS.
  float32 throughout — **no float64, no AMP/FP16** (MPS constraints).

### Claude's Discretion
- Concrete dataset schema on disk (`.npy`/`.npz` shards vs packed binary of encoded
  768-feature indices + label) — planner/researcher choose per throughput.
- DataLoader/feature-encoding implementation details, checkpoint cadence, optimizer
  (Adam default) and LR schedule — standard approaches unless research says otherwise.
- Which specific Lichess dump(s) and any time-control/rating filtering on the bulk
  ingest, subject to the wall-clock cap in D-08.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & contract (authoritative)
- `.planning/research/ARCHITECTURE.md` §"Component Responsibilities", §"Recommended
  Project Structure", §Pattern 1 — defines `nnue_format/` (shared, `schema.py` +
  `io.py`), the `training/` top-level layout (`label/`, `data/`, `model.py`,
  `train.py`, `export.py`), and the feature/perspective/forward-pass spec (768 inputs,
  `[stm_acc, opp_acc]` concat, ClippedReLU).
- `ance/eval/base.py` — the `Evaluator` Protocol (`evaluate(pos)->int`, cp
  side-to-move relative, `MATE=30000`). The Phase-5 `NnueEval` must satisfy this; the
  weights this phase exports feed it.

### Requirements & project constraints
- `.planning/REQUIREMENTS.md` — TRN-01…TRN-05 (exact wording).
- `.planning/ROADMAP.md` §"Phase 4" — goal + 5 success criteria.
- `.planning/PROJECT.md` — MPS constraints (no float64/AMP, `PYTORCH_ENABLE_MPS_FALLBACK=1`,
  verify `mps.is_available()`), 24 GB unified-memory ceiling, "heavy runs deferred to
  cloud" budget, NNUE reference architecture + quantization notes.
- `.planning/research/PITFALLS.md` — MPS regressions, K-scaling, labeling-command pitfalls.
- `.planning/research/STACK.md` — Lichess `[%eval]` reuse vs fresh Stockfish labeling
  tradeoff; PyTorch-MPS vs MLX; safetensors/npz export.

### External docs
- `nnue-pytorch/docs/nnue.md` (github.com/official-stockfish/nnue-pytorch) — the
  authoritative NNUE architecture + quantization reference cited by PROJECT.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ance/eval/base.py::Evaluator` + `MATE`: the swap seam the exported net ultimately
  serves; the weights contract must produce something a numpy evaluator can drive
  through this Protocol (Phase 5).
- `ance/board/position.py`: the thin port surface / board wrapper — feature extraction
  (position → 768 active indices) will read from `Position`.
- `chess.engine` (python-chess): used elsewhere only to *drive* external engines; here
  it drives Stockfish for the fresh-labeling pass (not for the engine's own UCI).

### Established Patterns
- **Evaluator seam is structurally enforced** — `tests/test_eval_seam.py` proves
  `negamax` never imports a concrete evaluator. Phase 4 does not touch search/eval;
  it only produces a weights file behind the `nnue_format` contract.
- `training/` is a **separate torch-only top-level, never shipped** into the engine
  runtime (ARCHITECTURE.md). Keep the torch dependency out of `ance/`.

### Integration Points
- Sole coupling = `nnue_format/` (`schema.py` arch/feature-set/shape ids + `io.py`
  save/load with validation). This phase writes via `export.py → nnue_format.save_net`;
  Phase 5 reads via `nnue_format.load_net` with zero torch.

</code_context>

<specifics>
## Specific Ideas

- K is *fitted*, not guessed — the pipeline includes an explicit calibration step that
  emits the chosen K into logs and the weights metadata for reproducibility.
- The wall-clock-capped run should be reproducible: fixed seeds, recorded dataset
  manifest, recorded labeling command, recorded fitted K.

</specifics>

<deferred>
## Deferred Ideas

- **Incremental accumulator** (make/unmake feature-delta hooks) — later optimization,
  not required for this phase's full-recompute training/export.
- **King-bucketed / larger nets, cloud/NVIDIA `bullet` training** — deferred to a
  future scale-up milestone per PROJECT.md; the ~8–12h M4 cap (D-08) is the ceiling here.

### Reviewed Todos (not folded)
- `2026-07-07-tool-02-depth-4-gauntlet-deferred.md` — depth-4 gauntlet; belongs to
  **Phase 5** (Elo gauntlet), not the training pipeline.
- `2026-07-08-phase2-encroissant-validation.md` — En Croissant watched validation
  game; a measurement/validation task tied to gameplay phases, not offline training.

</deferred>

---

*Phase: 4-Offline NNUE Training Pipeline*
*Context gathered: 2026-07-12*
