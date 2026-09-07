---
phase: 07-nnue-strength-recovery
plan: 03
subsystem: sidecar-install
tags: [nnue, sidecar, d-05, d-14, m4-train, blocked-resume]

requires:
  - phase: 07-nnue-strength-recovery
    provides: 07-01 ingest harness (--lichess-max-samples, 4-field FEN pad)
  - phase: 06-quiet-data-nnue-strength-gap
    provides: Phase 6 net at ance/eval/nnue/net.safetensors (must not be measured as Phase 7)
provides:
  - "install_phase7_net.py write_sidecar / install_export / M4_PIPELINE_ARGV"
  - "tests/training/test_phase7_sidecar.py (identity, RFC keys, install copy, argv pins)"
  - "07-USER-SETUP.md for the M4 sitting (Status Incomplete)"
  - "explicit blocked resume into 07-04 (no 07-NET-SIDECAR.json)"
affects: [sidecar, D-05, D-08, D-13, D-14, D-16, TOOL-04]

tech-stack:
  added: []
  patterns: [sidecar-writer, schema-arch-lock, rfc-json, blocked-m4-resume]

key-files:
  created:
    - .planning/phases/07-nnue-strength-recovery/install_phase7_net.py
    - tests/training/test_phase7_sidecar.py
    - .planning/phases/07-nnue-strength-recovery/07-USER-SETUP.md
  modified: []

key-decisions:
  - "keep-768x2-256-1: published arch stays 768x2-256-1 / board768; ARCH_ID and FEATURE_SET read from nnue_format.schema (D-05). schema.py / training/model.py / training/train.py not edited"
  - "M4 from-scratch train blocked on this CPU-only host (mps_available False). D-14 forbids a reduced CPU train. No fake 07-NET-SIDECAR.json"
  - "TOOL-04 remains listed on the plan but is not satisfied; this slice only ships the sidecar/install helper"

patterns-established:
  - "write_sidecar merges RESEARCH keys then re-locks phase 7, from_scratch true, arch_id/feature_set from schema"
  - "M4_PIPELINE_ARGV is the pinned RESEARCH CLI; never contains --resume-from-checkpoint; never executed here"
  - "install_export copies to ENGINE_NET; unit tests monkeypatch ENGINE_NET onto tmp_path"

requirements-completed:
  - TOOL-04

duration: 4min
completed: 2026-09-07
---

# Phase 7 Plan 03: Sidecar install helper Summary

**Sidecar writer + install helper lock `768x2-256-1` / `board768` from `nnue_format.schema` (D-05); M4 from-scratch train is blocked on this CPU-only host (D-14), so Plan 07-04 must write blocked evidence.**

TOOL-04 is copied into `requirements-completed` because the plan frontmatter lists it. This plan does **not** claim TOOL-04. No Phase 7 net was trained or installed. `07-NET-SIDECAR.json` was not written. `ance/eval/nnue/net.safetensors` was not overwritten. Phase 6 stays incomplete.

## Performance

- **Duration:** 4 min
- **Started:** 2026-09-07T17:23:22Z
- **Completed:** 2026-09-07T17:27:43Z
- **Tasks:** 3
- **Files modified:** 3 created

## Accomplishments

- Recorded D-05 one-way arch lock: **keep-768x2-256-1**. `write_sidecar` copies `ARCH_ID` / `FEATURE_SET` from `nnue_format.schema` at write time. No edits to `nnue_format/schema.py`, `training/model.py`, or `training/train.py`.
- Shipped `.planning/phases/07-nnue-strength-recovery/install_phase7_net.py`: `write_sidecar`, `install_export`, `sidecar_identity_payload`, `M4_PIPELINE_ARGV`, `REQUIRED_SIDECAR_KEYS`. RFC JSON via `json_safe_number` + `allow_nan=False`.
- Five sidecar unit tests green; `test_nnue_format_roundtrip.py` still green. Tests monkeypatch `SIDECAR_PATH` / `ENGINE_NET` onto `tmp_path`.
- M4 sitting blocked: `torch.backends.mps.is_available()` is False (`2.14.0+cpu`). Created `07-USER-SETUP.md` (Status Incomplete). No local `strength-run` and no `07-NET-SIDECAR.json`.

## Task Commits

1. **Task 1:** (decision keep-768x2-256-1; recorded in helper comments + this SUMMARY; no standalone file)
2. **Task 2 RED:** `50be48c` — `test(07-03): add failing tests for sidecar writer`
3. **Task 2 GREEN:** `b7e6f4b` — `feat(07-03): implement sidecar writer and install helper`
4. **Task 3:** `a18e023` — `docs(07-03): M4 sitting user-setup (blocked resume)`

## Files Created/Modified

- `.planning/phases/07-nnue-strength-recovery/install_phase7_net.py` — sidecar writer, install copy, pinned M4 argv
- `tests/training/test_phase7_sidecar.py` — five named sidecar/install/argv tests
- `.planning/phases/07-nnue-strength-recovery/07-USER-SETUP.md` — M4 sitting steps; Status Incomplete

## Decisions Made

- keep-768x2-256-1 (orchestrator checkpoint). change-arch out of scope.
- Task 3 human-action resumed **blocked**: this host has no MPS; D-14 forbids a CPU train; M4 sitting is not available. Plan 07-04 writes blocked evidence. Valid honest outcome.

## Deviations from Plan

None - plan executed exactly as written. Blocked M4 resume is the planned valid path into 07-04.

## Issues Encountered

None. Task 2 verify: 7 passed (`test_phase7_sidecar` + `test_nnue_format_roundtrip`). Cloud MPS check: False. Sidecar file absent. Packaged net untouched.

## User Setup Required

⚠️ **USER SETUP REQUIRED** — `.planning/phases/07-nnue-strength-recovery/07-USER-SETUP.md` (Status Incomplete)

On the PROJECT M4: MPS assert, `pip install -e '.[hf-ingest]'`, 2013-01 sha256, pinned CLI, `install_export` + `write_sidecar`, commit net + sidecar. Until then 07-04 must not measure `ance/eval/nnue/net.safetensors`.

## Next Phase Readiness

Ready for 07-04 (cloud measure closer run). Expect **blocked evidence** (`phase7_net_not_installed`) until the M4 sitting commits net + sidecar. Do not start a CPU train. Do not complete-phase 6. TOOL-04 still open. Do not execute `M4_PIPELINE_ARGV` on this host.

## Self-Check: PASSED

Sidecar helper tests green. No CPU train. No fake sidecar. Schema / trainer / packaged net unchanged.
