# Phase 5: NNUE Swap-In & Elo Gauntlet - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire a numpy `NnueEval` (full recompute, zero torch) behind the existing
`Evaluator` seam, load the Phase 4 exported weights, prove torch↔numpy parity
and perspective/sign goldens, then run a ≥1000-game fixed-opening gauntlet
showing measurable Elo gain of NNUE over handcrafted — the milestone payoff.

Delivers EVAL-03 and TOOL-04:
1. `NnueEval` implements `evaluate(position)->cp`, loads trained weights via
   `nnue_format`, passes parity against the torch forward pass on held-out FENs.
2. Golden perspective/sign tests: symmetric ≈ 0, color-mirror+STM-flip equal,
   SF sign agreement on a small won/lost suite.
3. Two gauntlet builds differ only in eval (search config identical).
4. ≥1000-game fixed-book gauntlet reports positive Elo with 95% CI lower bound > 0.

Out of scope (own phases / later): incremental accumulator (NNUE-01), HalfKP /
king buckets, cloud/big-net training, compiled hot-path port, lichess-bot,
v1.1 GUI.
</domain>

<decisions>
## Implementation Decisions

### Eval switch / two-build wiring
- **D-01:** Select evaluator via env var `ANCE_EVAL=handcrafted|nnue` (not CLI
  flags or UCI `setoption` for this phase). Matches existing `ANCE_DEBUG` pattern
  and works with cutechess `arg=` / python-chess arbiter alike.
- **D-02:** Default when unset is **handcrafted**. NNUE only when
  `ANCE_EVAL=nnue`. Keeps GUI/casual play on the known-good eval until TOOL-04
  proves a gain.
- **D-03:** Unknown / invalid `ANCE_EVAL` → **fail fast** (non-zero exit, stderr
  lists allowed values). No silent fallback.
- **D-04:** Both gauntlet builds use the **same** `python -m ance` argv; only
  `ANCE_EVAL` (and optionally `ANCE_NNUE_PATH`) differs. Diff-verify search
  config by comparing everything except the eval-selection env.

### Weights path contract
- **D-05:** Load order: `ANCE_NNUE_PATH` if set, else a **baked-in package
  default** under `ance/` (planner picks exact path, e.g.
  `ance/eval/nnue/net.safetensors`).
- **D-06:** Missing file or `nnue_format` validation failure when
  `ANCE_EVAL=nnue` → **fail fast at startup**. No silent handcrafted fallback.
- **D-07:** Copy the Phase 4 approved
  `.planning/phases/04-offline-nnue-training-pipeline/run-output/net.safetensors`
  into the package path and **track it in git** (~790 KB).
- **D-08:** Load-time checks are **strict**: `arch_id`, `feature_set`, and tensor
  shapes must match `nnue_format.schema` constants (`768x2-256-1`, `board768`).

### Elo gauntlet protocol (TOOL-04)
- **D-09:** Runner policy = Phase 3 **D-15**: prefer `cutechess-cli` when on
  PATH, else python-chess external arbiter. Do not block TOOL-04 on cutechess
  install. Evidence must record which runner was used. (Amends ROADMAP’s
  cutechess-only wording for this machine.)
- **D-10:** Fixed **≥1000 games** (no SPRT early-stop for the acceptance run).
  Report Elo + 95% CI; resume via existing gauntlet checkpoints.
- **D-11:** **Fixed depth** both sides (`go depth N`); planner/research picks N
  that fits a bounded overnight wall-clock. Not blitz clocks for the Elo proof.
- **D-12:** Pass criterion: Elo **point estimate > 0** and **95% CI lower bound
  > 0**.

### Parity & golden acceptance bar
- **D-13:** Torch ↔ numpy parity: **exact** integer cp after the shared
  float→int conversion on held-out FENs.
- **D-14:** Symmetric positions: eval **exactly 0** (tempo/startpos conventions
  as already established for handcrafted tests — research confirms which FENs).
- **D-15:** Color-mirror with STM flip: **exact equality** in integer cp.
- **D-16:** Stockfish comparison: **sign agreement** on a small fixed suite of
  clearly won/lost positions — not strict magnitude correlation to SF.

### Claude's Discretion
- Exact package-relative path for the baked-in net under `ance/`.
- Concrete held-out FEN suite size and contents for parity / goldens / SF-sign.
- Fixed search depth `N` and opening-book size for the overnight ≥1000-game run.
- Elo reporting formula details (BayesElo / logistic / simple score→Elo) as long
  as D-12’s CI lower-bound > 0 gate is met.
- How the diff-verify of “identical search config” is automated in tests/CI.

### Reviewed Todos
None folded into this phase (see Deferred).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 5" — goal + 4 success criteria (note D-09
  amends cutechess-only wording).
- `.planning/REQUIREMENTS.md` — EVAL-03, TOOL-04 (exact wording).
- `.planning/PROJECT.md` — core value, NNUE architecture, pure-Python ceiling,
  swappable-eval boundary.

### Prior phase decisions
- `.planning/phases/01-minimal-uci-engine-evaluator-seam/01-CONTEXT.md` —
  `Evaluator` Protocol / seam (D-00a).
- `.planning/phases/03-search-acceleration-time-management/03-CONTEXT.md` —
  gauntlet D-15…D-19 (runner, book, two builds, Wilson CI).
- `.planning/phases/04-offline-nnue-training-pipeline/04-CONTEXT.md` — arch
  N=256, safetensors/`nnue_format` (D-06/D-07), full recompute only.
- `.planning/phases/04-offline-nnue-training-pipeline/04-VERIFICATION.md` —
  approved D-08 net provenance and caveats (K=400 fallback, fresh-only data).

### Code & contract (authoritative)
- `ance/eval/base.py` — `Evaluator` Protocol + `MATE`.
- `ance/uci/loop.py` — current hardcoded `HandcraftedEval()` default; `ANCE_EVAL`
  wiring lands here.
- `ance/tools/gauntlet.py` — `EngineSpec`, cutechess/arbiter runners, checkpoint/resume.
- `nnue_format/schema.py`, `nnue_format/io.py` — load/validate contract (zero torch).
- `training/model.py` — torch `NNUE` forward pass (parity oracle only; not imported by `ance/`).
- `training/data/features.py` — 768-index feature encoding (must match engine-side features).
- `.planning/phases/04-offline-nnue-training-pipeline/run-output/net.safetensors` —
  source weights to copy into the package (D-07).

### External docs
- `nnue-pytorch/docs/nnue.md` (github.com/official-stockfish/nnue-pytorch) —
  architecture / perspective / ClippedReLU reference cited by PROJECT.md.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ance/eval/base.py::Evaluator` — the swap seam; `NnueEval` must satisfy it.
- `ance/eval/handcrafted.py::HandcraftedEval` — control build for the gauntlet.
- `nnue_format.io.load_net` — zero-torch weight load + metadata validation.
- `ance/tools/gauntlet.py` — TOOL-03 harness ready for TOOL-04 (argv builds,
  fixed book, checkpoint/resume, Wilson reporting, cutechess/arbiter).
- `ance/debug.py` — `ANCE_DEBUG` env pattern to mirror for `ANCE_EVAL` /
  `ANCE_NNUE_PATH`.
- Phase 4 approved `net.safetensors` (790 KB) with full provenance metadata.

### Established Patterns
- Search depends only on the `Evaluator` Protocol — never import concrete evals
  into `ance/search/`.
- `ance/` must never import `training/` (Phase 4 prohibition); parity tests may
  import torch/`training` only under `tests/` with appropriate skips.
- Gauntlet engines are subprocess UCI via argv; env vars are the injection
  surface for eval selection.

### Integration Points
- `ance/uci/loop.py` module-level `evaluator` — construct from `ANCE_EVAL` at
  startup (fail fast on bad env / bad weights).
- `python -m ance` → `loop.main()` — no argparse today; keep it that way (D-01).
- Gauntlet CLI: two `EngineSpec`s with identical argv, differing env in the
  launcher/wrapper the planner designs.
- Package data: copy net next to `NnueEval` (or under `ance/eval/nnue/`) and
  include in package data so default path resolves after install/editable.

</code_context>

<specifics>
## Specific Ideas

- Env-var eval switch preferred over UCI `setoption` for this milestone’s
  gauntlet honesty and simplicity.
- ROADMAP’s cutechess-only TOOL-04 wording is explicitly softened to D-15
  (arbiter acceptable) because `cutechess-cli` is absent on this machine.
- Exact integer parity/goldens are intentional — catch transpose/perspective
  bugs rather than tolerate drift.

</specifics>

<deferred>
## Deferred Ideas

None raised during discussion beyond already-scoped-out items (incremental
accumulator, big nets, GUI, compiled port).

### Reviewed Todos (not folded)
- `2026-07-07-tool-02-depth-4-gauntlet-deferred.md` — search/pruning backlog,
  not NNUE Elo.
- `2026-07-07-v1_1-gui-local-web-app.md` — v1.1 milestone.
- `2026-07-08-phase2-encroissant-validation.md` — already past Phase 2.

</deferred>

---

*Phase: 5-NNUE Swap-In & Elo Gauntlet*
*Context gathered: 2026-07-18*
