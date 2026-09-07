---
phase: 07-nnue-strength-recovery
status: clean
reviewed: "2026-09-07"
depth: standard
---

# Phase 7 Code Review (advisory)

Auto-invoked after execute-phase. Non-blocking.

## Scope

Wave 1–3 execution on `cursor/phase07-nnue-strength-recovery-5244`: ingest pad/caps, measure closer, sidecar helper, blocked closer run.

## Findings

No blocking issues.

### What looks correct

- 4-field HF FEN pad is a string append (` 0 16`) before STM sign-flip; no `chess.Board(fen).fen()` clock rewrite.
- Strength quiet filter passes `max_kept=120000`; non-strength leaves `None`.
- Closer `sidecar_identity_ok` requires file + phase 7 + `from_scratch is True` before diagnostics/probes/gauntlet.
- Blocked evidence is RFC JSON (`allow_nan False`), `gates_failed` D-14 and TOOL-04, no hand-green.
- `nnue_format/schema.py`, `training/model.py`, `training/train.py`, and packaged net were not modified.
- No CPU `run_pipeline` train on this host.

### Advisories (non-blocking)

1. `compare_phase6.n_merged` / `best_elo` stringify (`"19866"`, `"None"`). Tests lock the current baseline; optional cleanup after M4 sitting.
2. Closer/sidecar tests still use deprecated `SourceFileLoader.load_module()` (Phase 6 analog).
3. Three pre-existing not-slow failures remain outside this phase (`test_gauntlet_harness.py`, two `test_nnue_eval.py` goldens).

## Verdict

`clean` — ship the harness and blocked evidence. TOOL-04 stays open until the M4 sitting lands.
