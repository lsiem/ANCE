---
phase: 5
slug: nnue-swap-in-elo-gauntlet
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-18
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `05-RESEARCH.md` §Validation Architecture. Task IDs are filled by the planner/executor.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (configured via `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` (existing). Torch-dependent parity tests use `pytest.importorskip("torch")` / `@pytest.mark.torch`; `ance/` inference stays numpy-only. |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_nnue_eval.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q -m 'not slow'` |
| **Slow gauntlet** | `.venv/bin/python -m pytest tests/test_phase5_elo_evidence.py -x -m slow` |
| **Estimated runtime** | ~30–60 seconds (fast unit/integration); overnight for `@pytest.mark.slow` TOOL-04 evidence |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_nnue_eval.py -x -q` (plus gauntlet unit tests when `gauntlet.py` touched)
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -q -m 'not slow'`
- **Before `/gsd-verify-work`:** Full suite including `@pytest.mark.slow` TOOL-04 evidence must be green
- **Max feedback latency:** ~60 seconds (excluding slow Elo evidence)

---

## Per-Task Verification Map

> Task IDs reference `{phase}-{plan}-{task}` from Phase 5 PLAN.md files. Automated commands match plan `<verify><automated>` gates.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-2 | 05-01 | 1 | EVAL-03 | T-5-01 | NnueEval loads safetensors via strict `nnue_format`; implements Protocol | unit | `pytest tests/test_nnue_eval.py::test_nnue_loads_default_net -x` | ❌ W0 | ⬜ pending |
| 05-01-3 | 05-01 | 1 | EVAL-03 / D-13 | — | Torch↔numpy exact integer cp parity | integration (torch) | `pytest tests/test_nnue_eval.py -m torch -x` | ❌ W0 | ⬜ pending |
| 05-01-3 | 05-01 | 1 | EVAL-03 / D-03 | T-5-01 | Invalid `ANCE_EVAL` fail-fast (non-zero exit, stderr lists allowed) | subprocess | `pytest tests/test_nnue_eval.py::test_invalid_ance_eval_exits -x` | ❌ W0 | ⬜ pending |
| 05-01-2 | 05-01 | 1 | EVAL-03 / D-14 | — | Symmetric king-only positions score exactly 0 | unit | `pytest tests/test_nnue_eval.py::test_symmetric_positions_score_zero -x` | ❌ W0 | ⬜ pending |
| 05-01-3 | 05-01 | 1 | EVAL-03 / D-15 | — | Color-mirror + STM flip exact equality | unit | `pytest tests/test_nnue_eval.py::test_color_mirror_stm_flip -x` | ❌ W0 | ⬜ pending |
| 05-01-3 | 05-01 | 1 | EVAL-03 / D-16 | — | Stockfish sign agreement on won/lost suite | integration | `pytest tests/test_nnue_eval.py::test_stockfish_sign_agreement -x` | ❌ W0 | ⬜ pending |
| 05-02-2 | 05-02 | 2 | TOOL-04 / D-11 | — | Gauntlet depth mode + per-engine env injection | unit | `pytest tests/test_nnue_gauntlet_depth.py -x` | ❌ W0 | ⬜ pending |
| 05-02-3 | 05-02 | 2 | TOOL-04 / D-04 | — | Search-config identical except eval env | structural | `pytest tests/test_nnue_eval.py::test_search_config_unchanged_by_eval_env -x` | ❌ W0 | ⬜ pending |
| 05-03-2 | 05-03 | 3 | TOOL-04 / D-10–D-12 | — | ≥1000-game Elo point estimate > 0 and 95% CI lower bound > 0 | slow e2e | `pytest tests/test_phase5_elo_evidence.py -m slow -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `ance/eval/nnue/{features,inference,eval}.py` + git-tracked `net.safetensors` copy from Phase 4 run-output
- [ ] `ance/uci/loop.py` — `resolve_evaluator()` + fail-fast on bad env / bad weights
- [ ] `ance/tools/gauntlet.py` — `EngineSpec.env`, `--depth`, Elo fields in aggregate
- [ ] `tests/test_nnue_eval.py` — parity, goldens, env wiring
- [ ] `tests/test_nnue_gauntlet_depth.py` — harness contracts
- [ ] `tests/test_phase5_elo_evidence.py` — slow ≥1000-game gate + evidence JSON
- [ ] Optional: `tests/nnue_parity_helpers.py` — shared torch/numpy oracle

*Existing pytest infrastructure covers the framework; Wave 0 is new phase-specific files above.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Overnight ≥1000-game wall-clock completes and evidence is trustworthy | TOOL-04 / D-10–D-12 | Slow suite may be started manually / overnight; automated assertion still gates CI once complete | Confirm checkpoint resume works; inspect evidence JSON for runner used (arbiter vs cutechess), depth N, game count ≥1000, Elo + 95% CI; re-run once if CI lower bound is marginal |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s (excluding slow Elo evidence)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
