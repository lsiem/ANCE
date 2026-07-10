---
phase: 03
slug: search-acceleration-time-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-11
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (installed, configured via pyproject.toml) |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest -m "not slow" -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~10 seconds (fast suite); slow gauntlets are budgeted separately |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest -m "not slow" -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest -m "not slow" -q` (full slow suite deferred to phase-end evidence runs)
- **Before `/gsd-verify-work`:** Fast suite must be green; slow strength/clock gauntlets run per their plan budgets
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

*To be filled by the planner — one row per task with its automated verify command.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| — | — | — | SRCH-05, SRCH-06, SRCH-08, UCI-08, TOOL-03 | — | — | unit/integration | `.venv/bin/python -m pytest -m "not slow" -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — pytest, fast/slow markers, deterministic seeds, and the UCI subprocess test helpers (`tests/test_uci_info.py` fixtures) already exist. New test files land with their tasks (TDD), not as a separate Wave 0.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Watched GUI game under real clock (En Croissant) | SRCH-08 / UCI-08 | GUI interaction and human observation of live clock behavior | Load ANCE in En Croissant, play a blitz preset game, observe no flag fall and live info lines |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
