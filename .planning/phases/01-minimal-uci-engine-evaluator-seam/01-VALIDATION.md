---
phase: 1
slug: minimal-uci-engine-evaluator-seam
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `01-RESEARCH.md` § Validation Architecture. The Per-Task
> Verification Map is populated after PLAN.md tasks exist (planner / nyquist auditor).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none yet — Wave 0 creates `pyproject.toml`/`pytest.ini` + installs pytest into the arm64 venv |
| **Quick run command** | `python -m pytest tests/ -q -m "not slow"` |
| **Full suite command** | `python -m pytest tests/` |
| **Estimated runtime** | quick ~5s; full incl. 100-game random-mover gauntlet ~1–3 min (mark the gauntlet `slow`) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q -m "not slow"`
- **After every plan wave:** Run `python -m pytest tests/` (full suite, includes the gauntlet)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds for the quick suite (the 100/100 gauntlet is a wave-level, not per-commit, check)

---

## Per-Task Verification Map

> Populated after planning — task IDs come from PLAN.md. Each Phase 1 requirement
> already maps to a concrete pytest command in `01-RESEARCH.md` § Validation Architecture.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-XX-XX | XX | X | UCI-XX | — | N/A | unit | `python -m pytest tests/...` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Greenfield repo — no test infrastructure exists yet. Wave 0 must stand up:

- [ ] `pyproject.toml` (or `pytest.ini`) — pytest config + `slow` marker registration
- [ ] `tests/conftest.py` — shared fixtures (UCI engine subprocess driver, seeded RNG, sample FENs)
- [ ] pytest installed into the native arm64 venv alongside `chess` 1.11.2
- [ ] `tests/` package layout for: protocol-conformance, search/legality, eval-symmetry, robustness, and the random-mover gauntlet

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full legal game played in a real GUI without hanging/disqualification | TOOL-01, UCI-01 (success criterion 1) | Requires Cute Chess / Arena GUI installed + human observation of the handshake and a completed game | Install Cute Chess; register `<arm64-venv-python> -m ance`; play/observe one full game to a natural result |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (quick suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
