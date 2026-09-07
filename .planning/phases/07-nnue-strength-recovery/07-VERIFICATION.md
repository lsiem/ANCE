---
phase: 07-nnue-strength-recovery
verified: "2026-09-07T17:40:00Z"
status: human_needed
score: "harness 4/4 plans executed; TOOL-04 blocked (D-14, no Phase 7 sidecar)"
behavior_unverified: 1
requirements:
  TOOL-04: failed
deferred:
  - item: "M4 from-scratch train + commit net + 07-NET-SIDECAR.json"
    requirement: D-13 / D-16
    deferred_to: "human M4 sitting (07-USER-SETUP.md / 07-HUMAN-UAT.md)"
    reason: "Cloud Linux host is CPU-only (mps_avail False); D-14 forbids a reduced CPU train"
  - item: "16-game smoke → 200 → ≥1000 TOOL-04 gauntlet"
    requirement: TOOL-04
    deferred_to: "re-run post_train_close_07.py after sidecar+net land"
    reason: "Closer correctly wrote blocked evidence and did not measure the Phase 6 net"
---

# Phase 7: NNUE Strength Recovery Verification

## Goal

Retrain `768x2-256-1` from scratch on an HF-primary quiet corpus (padded 4-field
FENs, modest 2013-01 Lichess fill) and re-gate TOOL-04 at fixed depth 3 via
diagnostics → 16-game smoke → 200 → ≥1000, with honest blocked or useful-fail
evidence if the Phase 7 net is missing or weak.

**Verified:** 2026-09-07T17:40:00Z
**Status:** `human_needed` — ingest harness, closer, and sidecar helper are in
place; M4 train did not run; closer wrote honest blocked evidence (D-14).

Do not `/gsd-complete-phase 6` while TOOL-04 is open. Do not mark Phase 7
complete for TOOL-04.

## Goal Achievement

### Roadmap Success Criteria

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | HF-primary quiet corpus via 4-field FEN pad, mix 0.15, Lichess cap, max_kept | PASS (harness) | `row_to_sample` pads with `0 16`; `--lichess-max-samples`; `max_kept=120000` on strength quiet filter. Tests green. |
| 2 | Arch lock `768x2-256-1` / `board768`; no CPU train; sidecar/install helper | PASS (helper) | `install_phase7_net.py` reads `ARCH_ID`/`FEATURE_SET`; `nnue_format/schema.py` unchanged; MPS False on this host. |
| 3 | Closer: sidecar gate → diagnostics → 16 smoke → 200 → 1000 at depth 3 | PASS (mechanism) | `post_train_close_07.py` + `test_phase7_closer_evidence.py` (blocked, smoke abort, RFC JSON, compare_phase6). |
| 4 | TOOL-04 / honest blocked if Phase 7 net missing | PASS (honest blocked) / FAIL (TOOL-04) | `07-GAUNTLET-EVIDENCE.json`: `blocked.reason=phase7_net_not_installed`, `gates_failed` [D-14, TOOL-04], no gauntlet. |

**Roadmap score:** harness complete; TOOL-04 not satisfied (blocked, not a false green).

### Requirement Traceability

| Requirement | Result | Actual-code / measurement evidence |
|---|---|---|
| TOOL-04 | FAIL (blocked) | `07-GAUNTLET-EVIDENCE.json`: schema_version 1, `gauntlet.status=blocked`, `probe_smoke`/`probe_200` null, `gates_failed` D-14 and TOOL-04. Closer refused to measure `ance/eval/nnue/net.safetensors` without sidecar. |

### Plan Must-Have Verification

| Plan | Result | Verification |
|---|---|---|
| 07-01 | PASS | 4-field pad, mix 0.15, `--lichess-max-samples`, `max_kept`. Plan-level pytest 53 passed; wave re-run 71 passed. |
| 07-02 | PASS | Sidecar identity gate, SMOKE_GAMES=16, smoke abort, RFC shutouts, compare_phase6. |
| 07-03 | PASS (blocked resume) | Sidecar writer + tests green. Arch files unchanged. M4 train not run. No fake sidecar. |
| 07-04 | PASS (honest fail) | Closer wrote blocked evidence in ~0.2s. Evidence committed unchanged. |

## Confirmed Blocking Gaps

| Gap | Severity | Disposition |
|---|---|---|
| No Phase 7 from-scratch net / sidecar on this host | blocking (D-13 / D-14 / TOOL-04) | Human M4 sitting. Not a missing-harness defect. After net+sidecar commit, re-run `post_train_close_07.py`. |

## Human Verification Items

1. On the PROJECT M4: MPS train from scratch using `M4_PIPELINE_ARGV`, then `install_export` + `write_sidecar`, commit `ance/eval/nnue/net.safetensors` + `07-NET-SIDECAR.json`. See `07-USER-SETUP.md`.
2. After sidecar lands: cloud closer diagnostics → 16-game smoke → maybe 200 → maybe 1000. Do not raise SEARCH_DEPTH. Do not start a second train on smoke/200 fail.

## Automated Evidence

- Phase 7 harness pytest: **71 passed** in 6.27s (`test_hf_ingest`, `test_quiet_filter`, `test_run_pipeline_hf`, `test_phase7_closer_evidence`, `test_phase7_sidecar`, plus related training tests)
- Regression subset: **20 passed** (`test_nnue_accumulator`, `test_no_torch_leakage`, `test_cp_clamp`, `test_nnue_gauntlet_depth`)
- `07-GAUNTLET-EVIDENCE.json` — RFC JSON, `gates_failed`: D-14, TOOL-04
- `torch.backends.mps.is_available()` on this host: **False**

## Review-Only Advisories

- `compare_phase6.n_merged` serializes as the string `"19866"` and `best_elo` as `"None"` (copied from a stringified baseline). Numeric/null types would match RESEARCH more closely; closer tests assert the current baseline.
- `SourceFileLoader.load_module()` deprecation warnings in closer/sidecar tests (same pattern as Phase 6).
- Wave-level `pytest tests/ -m 'not slow'` still has 3 pre-existing failures outside this phase (`test_gauntlet_harness.py` StopIteration; two `test_nnue_eval.py` Phase-6-net goldens).

## Routing

Phase 7 plans are executed. TOOL-04 remains open. Next:

- M4 sitting per `/gsd:verify-work 7` human items (`07-HUMAN-UAT.md`)
- Then re-run the closer (or `/gsd:execute-phase 7 --gaps-only` if a gap plan is added)
- Do not complete-phase 6 or 7 until TOOL-04 is measured (pass or honest useful-fail after a real Phase 7 net)
