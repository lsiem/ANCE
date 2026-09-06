---
phase: "07"
slug: "nnue-strength-recovery"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-06"
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `07-RESEARCH.md` ## Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/training/test_hf_ingest.py tests/training/test_quiet_filter.py tests/training/test_phase6_closer_evidence.py tests/training/test_diagnostics_eval.py tests/training/test_lambda_schedule.py -q -x` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q -m 'not slow'` |
| **Estimated runtime** | ~30 seconds (quick) / ~2 minutes (full not-slow) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -q -m 'not slow'`
- **Before `/gsd-verify-work`:** Full not-slow suite must be green **and** `07-GAUNTLET-EVIDENCE.json` written (pass, useful-fail, or blocked)
- **Max feedback latency:** 120 seconds for not-slow suite

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-W0-01 | 01 | 0 | D-01 / D-03 | T-07-02 | Pad 4-field HF FEN; `chess.Board` reject illegal | unit | `.venv/bin/python -m pytest tests/training/test_hf_ingest.py -x -q` | ✅ file; ❌ pad cases | ⬜ pending |
| 07-W0-02 | 01 | 0 | D-02 | T-07-01 | `--lichess-max-samples` / `--min-has-result-rate 0.15` | unit | `.venv/bin/python -m pytest tests/training/test_quiet_filter.py -x -q` | ✅ file; ❌ 0.15 case | ⬜ pending |
| 07-W0-03 | 02 | 0 | TOOL-04 / D-10 / D-14 | T-07-01 | Smoke abort + blocked sidecar JSON | unit | `.venv/bin/python -m pytest tests/training/test_phase7_closer_evidence.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 07-01 | 01 | 1 | D-01–D-06 | T-07-02 | HF pad + mix + M4 CLI flags exist | unit | `.venv/bin/python -m pytest tests/training/test_hf_ingest.py tests/training/test_quiet_filter.py tests/training/test_lambda_schedule.py -x -q` | ✅ / ❌ W0 | ⬜ pending |
| 07-02 | 02 | 2 | TOOL-04 / D-09–D-16 | T-07-01 | Closer evidence schema + no CPU train | unit | `.venv/bin/python -m pytest tests/training/test_phase7_closer_evidence.py tests/test_nnue_gauntlet_depth.py -x -q` | ❌ W0 / ✅ | ⬜ pending |
| 07-03 | 03 | 3 | TOOL-04 / D-12 | — | ≥1000-game Elo CI (if 200 passes) | closer | closer script writes `07-GAUNTLET-EVIDENCE.json` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `training/data/hf_ingest.py` — pad 4-field FENs (` 0 16`); test the official sample FEN
- [ ] `training/run_pipeline.py` — `--lichess-max-samples` (default `None` = today’s time cap)
- [ ] `training/data/quiet_filter.py` — optional `max_kept` early-stop + per-source stats
- [ ] `tests/training/test_phase7_closer_evidence.py` — blocked / smoke abort / `compare_phase6` / RFC JSON
- [ ] `.planning/phases/07-nnue-strength-recovery/post_train_close_07.py` — copy 06 + smoke + sidecar gate
- [ ] Framework install: none — pytest already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| M4 MPS train from scratch + in-train 12-game probes | D-13 / D-15 / D-07 | Needs Apple Silicon MPS; this cloud host is CPU-only | Run pinned M4 CLI in RESEARCH; commit `net.safetensors` + `07-NET-SIDECAR.json` |
| 16-game smoke → 200 → optional ≥1000 TOOL-04 | TOOL-04 / D-09–D-12 | 18h wall-clock; not pytest `-m slow` overnight | Cloud closer after sidecar is present; write `07-GAUNTLET-EVIDENCE.json` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s for not-slow suite
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
