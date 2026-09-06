# Phase 7: NNUE strength recovery - Context

**Gathered:** 2026-09-06
**Status:** Ready for planning

<domain>
## Phase Boundary

A second strength attempt after Phase 6’s quiet 2013-01 net (`n_merged=19866`)
passed polarity/color-flip diagnostics and then lost the depth-3 probe **0–200**.
Phase 7 retrains `(768→256)×2→1` on a **Hugging Face–primary** labeled corpus
with a **modest Lichess PGN fill**, keeps the quiet filter, lightly retunes λ /
fen-skip / epochs, exports a net from scratch, and re-runs the Phase 6
measurement ladder (diagnostics → tiny play smoke → 200 → ≥1000 TOOL-04 at
depth 3).

Delivers another honest TOOL-04 / D-12 measurement. The phase **passes** only
if Elo > 0 and 95% CI low > 0 at ≥1000 games. A probe that is clearly stronger
than Phase 6’s 0–200 is a useful documented fail, not a pass.

Out of scope (own phases / already locked out): HalfKA / king buckets, hidden
width ≠ 256, self-play RL, NVIDIA `bullet` / CUDA, compiled hot-path port,
lichess-bot, v1.1 GUI, completing Phase 6 (`/gsd-complete-phase 6` stays
blocked while TOOL-04 is open).

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 7: NNUE strength recovery" — stub goal; this
  CONTEXT is the scope until `/gsd-plan-phase 7`.
- `.planning/REQUIREMENTS.md` — TOOL-04 wording (Elo > 0, CI low > 0).
- `.planning/PROJECT.md` — M4/MPS, `(768→N)×2→1`, no self-play RL, no compiled
  port, no NVIDIA bullet this milestone.

### Prior phase decisions & evidence
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-CONTEXT.md` — D-01–D-04
  (`ANCE_EVAL`), D-10–D-12 (TOOL-04 protocol).
- `.planning/phases/04-offline-nnue-training-pipeline/04-CONTEXT.md` — D-04–D-09
  (fitted K, N=256, safetensors, MPS gate, float32).
- `.planning/phases/06-quiet-data-nnue-strength-gap/06-VERIFICATION.md` — 3/4
  pass; TOOL-04 fail; do not complete-phase 6.
- `.planning/phases/06-quiet-data-nnue-strength-gap/06-06-SUMMARY.md` — closer
  narrative.
- `.planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json` —
  0–200 baseline to beat and to compare.

### Code & contract (authoritative)
- `training/data/hf_ingest.py` — HF stream, `_HF_DEFAULT_REPO`, STM sign flip,
  `game_result=None`.
- `training/run_pipeline.py` — `--hf-dataset`, `--hf-max-positions`,
  `--strength-corpus` requires `--lichess-zst`, `enforce_corpus_mix`.
- `training/data/quiet_filter.py` — quiet reject rules + mix guards.
- `training/train.py` — AdamW, cosine LR, λ schedule, fen-skip, best-val /
  best-Elo export.
- `training/elo_probe.py` — in-train probe hook.
- `nnue_format/schema.py` — `768x2-256-1` / `board768`.
- `ance/eval/nnue/net.safetensors` — current Phase 6 install (replace after M4
  train; do not fine-tune).

### External docs
- Hugging Face `Lichess/chess-position-evaluations` — 395M parquet positions,
  CC0-1.0; cp/mate white-relative (ingest already negates for black STM).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `training/data/hf_ingest.py` + `hf-ingest` extras (`huggingface_hub`,
  `pyarrow`) — already streams the chosen repo.
- `training/run_pipeline.py --strength-corpus --quiet-filter --lichess-zst
  --hf-dataset` — mix order is lichess → HF → fresh; first-wins FEN dedup.
- `training/train.py::run_training` — λ 1.0→0.75, fen-skip, Elo-probe knobs
  already exist (Phase 6 strength-run used `--elo-probe-every 0`).
- `training/diagnostics_eval.py` — startpos / material / color-flip gate.
- Phase 6 closer + `06-GAUNTLET-EVIDENCE.json` schema — copy for 07 measure /
  blocked-evidence.

### Established Patterns
- `ance/` must not import `training/`.
- Strength corpus still requires a Lichess zst so ≥50% rows can carry
  `game_result` unless planning explicitly lowers that floor to match D-02’s
  modest fill (discretion, not a discuss lock).
- Honest `gates_failed` over retry-until-green.
- Packaged net is git-tracked safetensors (~0.8 MB class).

### Integration Points
- M4: pipeline + `run_training` + in-train `elo_probe` → overwrite
  `ance/eval/nnue/net.safetensors` + sidecar.
- Cloud closer: diagnostics → smoke → 200 → maybe 1000; `ANCE_EVAL=nnue` vs
  handcrafted; same `python -m ance` argv (Phase 5 D-04).
- If net missing: blocked evidence JSON, no CPU train (D-14).

</code_context>

<specifics>
## Specific Ideas

- Phase 6 failed from **small quiet corpus + val-loss export**, not from a
  missing harness. Phase 7 changes **source scale and net-selection**, not the
  TOOL-04 contract.
- User deferred numeric knobs to Claude; planner should pick conservative
  values that fit D-15 (M4 one sitting) rather than maximize positions.
- Compare every 07 probe number to Phase 6 `06-GAUNTLET-EVIDENCE.json`
  (0/200/0, score 0.0, Elo −∞ / JSON null, CI high −686.6).

</specifics>

<deferred>
## Deferred Ideas

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

</deferred>

---

*Phase: 7-NNUE strength recovery*
*Context gathered: 2026-09-06*
