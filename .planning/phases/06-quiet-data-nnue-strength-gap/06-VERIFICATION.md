---
phase: 06-quiet-data-nnue-strength-gap
verified: "2026-09-06T14:10:00Z"
status: failed
score: "3/4 roadmap success criteria; TOOL-04 failed (200-game probe 0-200)"
behavior_unverified: 0
requirements:
  TOOL-04: failed
deferred:
  - item: "≥1000-game depth-3 TOOL-04 gauntlet"
    requirement: TOOL-04
    deferred_to: "next strength-recovery phase (larger result-bearing corpus / different recipe)"
    reason: "200-game probe gate failed (0–200, elo_ci_low not > 0); closer correctly skipped the 1000-game run"
---

# Phase 6: Quiet-Data NNUE Strength Gap Verification

## Goal

Rebuild the training distribution around quiet, result-bearing positions and
Stockfish-aligned trainer controls so NNUE can pass TOOL-04 (`elo_ci_low > 0`)
at fixed depth 3.

**Verified:** 2026-09-06T14:10:00Z
**Status:** `failed` — harness and honest measurement are in place; strength gate is not met.

`/gsd-progress --next` routed here because all Phase 6 plans are executed,
`workflow.verifier` is true, and no verification report existed.

## Goal Achievement

### Roadmap Success Criteria

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Strength corpus prefers Lichess PGN + HF fill; fresh ≤10%; ≥50% `game_result`; K fitted | PASS (mechanism + fitted K) | `enforce_corpus_mix` + `--strength-corpus` require `--lichess-zst`, cap fresh, raise if `has_result` < 50%. Installed net metadata: `n_merged=19866`, `k_scale=451.45` (not fallback 400). Per-run `has_result_rate` is not stored in the safetensors metadata. |
| 2 | Quiet filter rejects checks, capture-bestmoves, `|static − qsearch| > 60`; cp clamp ±10000 | PASS | `training/data/quiet_filter.py`, `cp_clamp.py` (`DEFAULT_CP_CLAMP=10000`). `tests/training/test_quiet_filter.py` + `test_cp_clamp.py` green. |
| 3 | Trainer λ 1.0→0.75, fen-skip 3, resume-from, mid-train Elo probes; best-by-Elo when probes ran | PASS (mechanism) | CLI + `run_training` wired. This strength-run used `--elo-probe-every 0`; metadata `best_elo=None` (best-val export, not best-Elo). |
| 4 | Diagnostics pass; 200-game probe then ≥1000 TOOL-04; accumulator parity; no HalfKA | FAIL | Diagnostics **ok**. Probe **0–200** at depth 3, all checkmate. ≥1000 skipped. Accumulator parity tests pass. Arch remains `768x2-256-1` / `board768`. |

**Roadmap score:** 3/4 (criterion 4 failed).

### Requirement Traceability

| Requirement | Result | Actual-code / measurement evidence |
|---|---|---|
| TOOL-04 | FAIL | `06-GAUNTLET-EVIDENCE.json`: 200 games, W/L/D 0/200/0, score_rate 0.0, Wilson 0.00–0.0188, `elo`/`elo_ci_low` JSON null (−∞), `elo_ci_high` −686.6, `gates_failed` [D-12, TOOL-04]. No ≥1000-game row. |

### Plan Must-Have Verification

| Plan | Result | Verification |
|---|---|---|
| 06-01 | PASS | Quiet filter + mix guards + tests present and green. |
| 06-02 | PASS | λ schedule, fen-skip, `--resume-from-checkpoint` in `train.py` / CLI. |
| 06-03 | PASS | `training/elo_probe.py` + mid-train hook; unused on this run (`elo-probe-every 0`). |
| 06-04 | PASS | Diagnostics + closer + evidence schema tests. |
| 06-05 | PASS | `tests/test_nnue_accumulator.py` + `06-NPS-BENCH.json`. |
| 06-06 | PASS (honest fail) | Diagnostics polarity pass; 200-game probe completed; closer stopped; evidence committed with honest `gates_failed`. |

## Confirmed Blocking Gaps

| Gap | Severity | Disposition |
|---|---|---|
| Quiet-data net is far weaker than handcrafted at depth 3 (0–200, CI high −686.6) | blocking (TOOL-04 / D-12) | Not a missing-harness defect. Next strength attempt needs a much larger result-bearing corpus or a different trainer recipe — a new phase, not a 06-07 code-gap plan. |

## Review-Only Advisories

- **D-14 exact-0 golden:** packaged net scores startpos **+13** (`test_symmetric_positions_score_zero` fails). Phase 6 diagnostics allow ±50 cp and pass.
- **Stockfish sign:** one rook-up vs pawns case scores **−197** (`test_stockfish_sign_agreement`).
- **Mix-rate provenance:** `has_result_rate` / fresh share were enforced at train time but not written into net metadata.
- **Phase 5 goldens vs this net:** EVAL-03 goldens written for an earlier net; they are not Phase 6 closer gates.

## Automated Evidence

- `.venv/bin/python -m pytest tests/training/test_quiet_filter.py tests/training/test_cp_clamp.py tests/training/test_lambda_schedule.py tests/training/test_diagnostics_eval.py tests/training/test_phase6_closer_evidence.py tests/training/test_nps_bench.py tests/test_nnue_accumulator.py tests/test_nnue_gauntlet_depth.py -q` — **33 passed** in 2.18s
- `.venv/bin/python -m training.diagnostics_eval --net ance/eval/nnue/net.safetensors` — **ok** (startpos +13, rook-up +160, queen-up +138, color-flip 12/12)
- `.planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json` — RFC JSON, `gates_failed`: D-12, TOOL-04

## Routing

Do **not** `/gsd-complete-phase` — TOOL-04 remains open on the milestone.

Next `/gsd-progress --next`: `/gsd-discuss-phase` (or `/gsd-plan-phase`) for a **Phase 7** strength-recovery slice (larger Lichess dump / different recipe). `--force` is not required; this is not a skipped safety gate, it is a failed acceptance gate.
