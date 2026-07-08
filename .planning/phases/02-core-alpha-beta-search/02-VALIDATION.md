---
phase: 02
slug: core-alpha-beta-search
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-08
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest -m "not slow" -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~45s fast / ~12min with slow gauntlet |

---

## Sampling Rate

- **After every task commit:** Run `pytest -m "not slow" -q`
- **After every plan wave:** Run `pytest -m "not slow" -q`
- **Before `/gsd-verify-work`:** Full suite including `@pytest.mark.slow` must be green
- **Max feedback latency:** 60 seconds (fast suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SRCH-02 | T-02-01 | N/A | unit | `pytest tests/test_alpha_beta.py -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | SRCH-02 | T-02-01 | N/A | unit | `pytest tests/test_alpha_beta.py -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | SRCH-04 | T-02-02 | N/A | unit | `pytest tests/test_quiescence.py -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | SRCH-04 | T-02-02 | N/A | unit | `pytest tests/test_quiescence.py -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | SRCH-03, SRCH-07 | T-02-03 | N/A | unit | `pytest tests/test_iterative_deepening.py -q` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 3 | SRCH-03, SRCH-07 | T-02-03 | N/A | unit | `pytest tests/test_iterative_deepening.py -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 4 | UCI-11 | T-02-04 | N/A | integration | `pytest tests/test_uci_info.py -q` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 4 | UCI-11, D-09, D-12 | T-02-04 | N/A | integration | `pytest tests/test_uci_info.py tests/test_go_bestmove.py -q` | ✅ | ⬜ pending |
| 02-05-01 | 05 | 5 | D-13 | — | N/A | unit | `pytest tests/test_tactical_search.py -q` | ❌ W0 | ⬜ pending |
| 02-05-02 | 05 | 5 | D-01, D-14 | — | N/A | slow | `pytest -m slow tests/test_random_mover_gauntlet.py tests/test_depth_vs_depth.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing pytest + subprocess harness from Phase 1 covers infrastructure. New test files created in-plan (not a separate Wave 0).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| En Croissant Unlimited deepens | D-12 | GUI-specific | Load engine, Unlimited analysis, confirm `info depth` lines stream until Stop |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s (fast suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
