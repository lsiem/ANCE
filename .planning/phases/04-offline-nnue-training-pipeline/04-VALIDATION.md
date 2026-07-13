---
phase: 4
slug: offline-nnue-training-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-13
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `04-RESEARCH.md` §Validation Architecture. Task IDs are filled by the planner/executor.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already configured via `pyproject.toml [tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Config file** | `pyproject.toml` (existing). Isolate torch under `tests/training/conftest.py` with `pytest.importorskip("torch")` so the torch-free `ance/` suite never has to install torch. The `nnue_format` roundtrip test must NOT be skipped when torch is absent (numpy-only by design). |
| **Quick run command** | `pytest tests/training/ -x -q` |
| **Full suite command** | `pytest tests/ tests/training/ -q` |
| **Estimated runtime** | ~30 seconds (fast unit/smoke tests on synthetic/fixture data — NOT the real multi-hour pipeline) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/training/ -x -q`
- **After every plan wave:** Run `pytest tests/ tests/training/ -q` (confirms the torch-only addition never leaks into `ance/`)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Task IDs are assigned at planning time. Rows below are the requirement/decision → test mapping from research; the planner attaches each to a concrete `{4}-{plan}-{task}` id.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1 | TRN-05 | — | MPS gate skips parity math gracefully if MPS unavailable | unit/smoke | `pytest tests/training/test_mps_gate.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | TRN-04 / D-07 | T-4-02 (no pickle load of untrusted `.pt`; ship safetensors) | numpy-only roundtrip validates arch_id/feature_set_id/shapes | unit | `pytest tests/training/test_nnue_format_roundtrip.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | TRN-02 / D-03 | — | no FEN appears in both train and val splits | unit | `pytest tests/training/test_split_no_leakage.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | D-01 / D-05 | T-4-01 (skip-and-log malformed games) | Lichess `[%eval]` White-relative value sign-flips for Black-to-move | unit | `pytest tests/training/test_lichess_ingest_sign.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | D-04 | — | `curve_fit` recovers a known K from synthetic sigmoid data within tolerance | unit | `pytest tests/training/test_kfit_calibration.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | TRN-01 | T-4-01 / T-4-03 | labeler uses normalized UCI cp (`info["score"].relative`), records exact command; skips cleanly if `stockfish` absent | integration | `pytest tests/training/test_stockfish_labeler.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | TRN-03 | — | net trains on MPS-or-CPU against sigmoid-WDL target, val loss decreases on a short smoke run | integration/smoke | `pytest tests/training/test_train_loop_smoke.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/training/__init__.py` + `tests/training/conftest.py` — new test package; `conftest.py` `pytest.importorskip("torch")` for torch-dependent tests only (roundtrip test stays torch-free)
- [ ] `tests/training/test_nnue_format_roundtrip.py` — TRN-04 / D-07 (write first — needs no torch, no Stockfish, no real data)
- [ ] `tests/training/test_mps_gate.py` — TRN-05
- [ ] `tests/training/test_split_no_leakage.py` — TRN-02 / D-03
- [ ] `tests/training/test_kfit_calibration.py` — D-04
- [ ] `tests/training/test_lichess_ingest_sign.py` — D-01 / D-05 sign correction (Pitfall #3)
- [ ] `tests/training/test_stockfish_labeler.py` — TRN-01 (skips cleanly if `stockfish` binary absent from PATH)
- [ ] `tests/training/test_train_loop_smoke.py` — TRN-03 (short synthetic run)
- [ ] Framework install: `pip install torch numpy safetensors zstandard scipy tqdm` — none currently in `.venv`
- [ ] External tool install: `brew install stockfish` — not currently installed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The overnight run's real artifacts are trustworthy | TRN-03 / D-08 | The real ~8–12h training run cannot be an automated per-commit test; automated tests validate *mechanism* (leakage, roundtrip, K-fit math), not the trained net's chess strength (that is Phase 5's gauntlet) | Inspect the produced dataset manifest, fitted K (logged + in weights metadata), checkpoint, and exported `.safetensors`; confirm the recorded validation-loss curve is monotonically decreasing and the fitted K is within a plausible range (~150–600) |
| MPS actually engaged (vs silent CPU fallback) | TRN-05 / D-09 | macOS 26 (Tahoe) has a reported `mps.is_available()==False` regression; whether GPU or CPU was used is a runtime fact of the target machine | Read the harness's device banner at run start; if CPU fallback, confirm the wall-clock cap (D-08) was re-budgeted accordingly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
