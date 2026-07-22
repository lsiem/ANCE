---
phase: 05-nnue-swap-in-elo-gauntlet
plan: 03
subsystem: tools
tags: [gauntlet, elo, tool-04, d-12, evidence, nnue]

requires:
  - phase: 05-nnue-swap-in-elo-gauntlet
    provides: Fixed-depth gauntlet + EngineSpec.env + Elo/Wilson fields from Plan 05-02
  - phase: 05-nnue-swap-in-elo-gauntlet
    provides: Installed NnueEval + net.safetensors from Plan 05-01 / HF scale export
provides:
  - Committed 05-GAUNTLET-EVIDENCE.json (≥1000 games, depth 3, honest gates_failed)
  - D-12 assertion helpers + slow TOOL-04 gate test
affects:
  - Phase 05 gap plan 05-04 (retrain / re-evidence for TOOL-04)

tech-stack:
  added: []
  patterns:
    - Durable checkpoint resume for multi-day depth-3 gauntlets
    - Honest gates_failed when Elo CI does not clear D-12

key-files:
  created:
    - tests/test_phase5_elo_evidence.py
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/run_gauntlet_05_03.py
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/finalize_05_03_evidence.py
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/watch_and_resume_cloud.sh
  modified: []

key-decisions:
  - "Evidence committed with gates_failed=[D-12,TOOL-04] — do not claim milestone payoff"
  - "Discarded mixed-net mid-run checkpoint after PR #5 HF weights landed; restarted clean"
  - "Acceptance depth remains N=3; failure is strength/data, not harness"

patterns-established:
  - "TOOL-04 evidence JSON always records games/mode/depth/runner/env diff even on gate fail"
  - "Inf Elo serialized as null in committed JSON for strict parsers"

requirements-completed: []  # TOOL-04 NOT closed — see gates_failed + Plan 05-04

coverage:
  - id: D1
    description: Fast D-12/D-10 helpers + load_evidence schema tests
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_phase5_elo_evidence.py
        status: pass
    human_judgment: false
  - id: D2
    description: ≥1000-game fixed-depth NNUE vs handcrafted evidence artifact
    requirement: TOOL-04
    verification:
      - kind: e2e
        ref: .planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json
        status: fail
    human_judgment: false
  - id: D3
    description: D-12 Elo point estimate > 0 and elo_ci_low > 0
    requirement: TOOL-04
    verification:
      - kind: e2e
        ref: tests/test_phase5_elo_evidence.py#test_phase5_thousand_game_nnue_vs_handcrafted_evidence
        status: fail
    human_judgment: false

duration: ~36h wall (clean gauntlet) + prior mixed-net attempt
completed: 2026-07-22
status: complete-with-failed-gates
---

# Phase 05 Plan 03: Elo Gauntlet Evidence Summary

**Honest ≥1000-game depth-3 NNUE vs handcrafted evidence — D-12 / TOOL-04 failed (0–1000–0)**

## Performance

- **Duration:** ~35.8 h elapsed search time on clean run (`elapsed_s` ≈ 128821)
- **Started (clean):** 2026-07-20T17:57Z
- **Completed:** 2026-07-22T05:47Z
- **Tasks:** 2
- **Files modified:** helpers + evidence + planning docs

## Result (headline)

| Field | Value |
|-------|-------|
| Games | 1000 |
| Mode / depth | `fixed_depth` / 3 |
| W–L–D | **0–1000–0** |
| Score rate | 0.0 |
| Elo / CI | null (−∞) / null … −966 |
| Runner | arbiter |
| gates_passed | `[]` |
| gates_failed | `["D-12", "TOOL-04"]` |

Engine A `ANCE_EVAL=nnue` vs Engine B `ANCE_EVAL=handcrafted`; identical `python -m ance` argv.

## Accomplishments

- Task 1: D-12 helpers + fast contract tests (`assert_positive_elo_with_ci`, `assert_minimum_games`, `load_evidence`)
- Task 2: Durable clean 1000-game gauntlet after discarding a mixed Phase-4/HF-net checkpoint
- Committed machine-readable `05-GAUNTLET-EVIDENCE.json` with honest `gates_failed`
- Cloud resume helpers: `run_gauntlet_05_03.py`, `watch_and_resume_cloud.sh`, `finalize_05_03_evidence.py`

## Task Commits

1. **Task 1: D-12 assertion helpers + fast contract tests** — `bdfda2d` (test)
2. **Task 2: ≥1000-game evidence run** — this commit (evidence + SUMMARY; slow pytest assertion fails as expected)

## Exact command line

```text
/workspace/.venv/bin/python -m ance.tools.gauntlet --games 1000 --tc 30+0.3 --depth 3 --openings /workspace/ance/tools/openings.epd --output .planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json --max-halfmoves 160 --engine-a '/workspace/.venv/bin/python -m ance' --engine-b '/workspace/.venv/bin/python -m ance' --engine-a-name nnue --engine-b-name handcrafted --runner arbiter --budget-seconds 172800
```

Durable wrapper used in cloud:

```bash
export PATH="/usr/games:$PATH"
.venv/bin/python -u .planning/phases/05-nnue-swap-in-elo-gauntlet/run_gauntlet_05_03.py
.venv/bin/python .planning/phases/05-nnue-swap-in-elo-gauntlet/finalize_05_03_evidence.py
```

## Decisions Made

- Restarted clean after PR #5 installed HF `net.safetensors` mid-run (~game 684 of the first attempt)
- Kept depth=3 / 1000 games (D-10/D-11); did not lower the bar to claim TOOL-04
- Documented HF net weaknesses (startpos ≠ 0, inverted material on sample rook-up) as training/data issues

## Deviations from Plan

### Expected gate failure (not auto-fixed)

**1. [D-12 / TOOL-04] NNUE lost all 1000 games**
- **Found during:** Task 2 evidence run
- **Issue:** HF-primary net (~37k unique positions after 250k ingest dedup) is far weaker than handcrafted at depth 3
- **Disposition:** Commit honest evidence; open Plan **05-04** gap closure (retrain + re-gauntlet)
- **Files:** `05-GAUNTLET-EVIDENCE.json`, `05-04-PLAN.md`

**Total deviations:** 1 expected milestone failure (no scope cheat)

## Issues Encountered

- Wall-clock ~150 s/game → ~36 h for 1000 games (well above RESEARCH 4–8 h estimate)
- Mid-run net swap invalidated first checkpoint; discarded as `05-gauntlet-checkpoint.mixed-net-discarded.json` (gitignored)

## Next Phase Readiness

- Plan **05-04** (gap): scale/improve training data, reinstall net, re-run D-12 evidence until `elo_ci_low > 0`
- Phase 5 milestone incomplete until TOOL-04 clears
- Fast lane remains green: `pytest tests/test_phase5_elo_evidence.py -m "not slow" -q`

## Verification Results

- `pytest tests/test_phase5_elo_evidence.py -m "not slow" -q` — **4 passed**, 1 deselected
- Slow gate `pytest … -m slow` — **fails** on `assert_positive_elo_with_ci` (expected with this net)
- Evidence present with `games=1000`, `depth=3`, `mode=fixed_depth`, env-only `ANCE_EVAL` diff

## Self-Check

- [x] Evidence JSON on disk and loadable via `load_evidence`
- [x] Task 1 commit present (`bdfda2d`)
- [x] Honest `gates_failed` — no false TOOL-04 claim
- [x] Gap plan 05-04 opened for follow-up

---
*Phase: 05-nnue-swap-in-elo-gauntlet*
*Completed: 2026-07-22 (gates failed)*
