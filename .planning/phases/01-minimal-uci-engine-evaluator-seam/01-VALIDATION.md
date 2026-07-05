---
phase: 1
slug: minimal-uci-engine-evaluator-seam
status: final
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `01-RESEARCH.md` § Validation Architecture. The Per-Task
> Verification Map below is derived from the final PLAN.md tasks
> (Plans 01-01 through 01-06). `wave_0_complete` flips to `true` only
> once execution actually runs Plan 01-01's Wave 0 setup task.

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

> Derived from the final PLAN.md tasks (Plans 01-01 through 01-06, all
> `wave`/`depends_on` values as committed). Automated commands are the
> literal `<automated>` verify strings from each task.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01-01 | 1 | — (pre-install gate) | T-01-SC | Human verifies `chess`/`pytest` package identity on PyPI before install | manual (checkpoint:human-verify) | N/A — blocking human checkpoint | ❌ no code yet | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | — (Wave 0 infra) | — | arm64 venv + pinned deps + pytest config, no code path yet | integration | `.venv/bin/python -m pytest --collect-only -q` | ❌ Wave 0 creates `pyproject.toml` | ⬜ pending |
| 01-01-T3 | 01-01 | 1 | UCI-01, UCI-02, UCI-12 | T-01-01, T-01-02 | Non-blocking handshake; unknown leading tokens skipped from day one; search never runs on the reader thread | integration (subprocess) | `.venv/bin/python -m pytest tests/test_uci_handshake.py -q -x` | ❌ created by this task | ⬜ pending |
| 01-02-T1 | 01-02 | 2 | UCI-04, SRCH-01 | T-01-03 | `try_set_fen`/`try_push_uci_moves` build a candidate board locally before committing | unit | `.venv/bin/python -m pytest tests/test_position_command.py -k "startpos or has_no_legal_moves" -q -x` | ❌ created by this task | ⬜ pending |
| 01-02-T2 | 01-02 | 2 | UCI-03, UCI-05 | T-01-03, T-01-04 | Malformed FEN / illegal move rejected, board left untouched; unknown tokens ignored; `ucinewgame` resets to startpos | integration (subprocess) | `.venv/bin/python -m pytest tests/test_position_command.py -q -x` | ❌ extends 01-02-T1's file | ⬜ pending |
| 01-02-T3 | 01-02 | 2 | (D-18, grouped under this plan's requirement set) | T-01-05 | Debug channel is stderr-only and off by default | integration (subprocess) | `.venv/bin/python -m pytest tests/test_position_command.py -k debug -q -x` | ❌ extends 01-02-T1/T2's file | ⬜ pending |
| 01-03-T1 | 01-03 | 3 | EVAL-01 | — | `Evaluator` Protocol + bootstrap evaluators are side-to-move relative (D-07) | unit | `.venv/bin/python -m pytest tests/test_eval_seam.py -q -x` | ❌ created by this task | ⬜ pending |
| 01-03-T2 | 01-03 | 3 | EVAL-01, UCI-06 (search substrate) | T-01-07 | `stop_flag` polled at sampled node intervals + every root move; structural proof `negamax.py` imports no concrete evaluator | unit + structural | `.venv/bin/python -m pytest tests/test_eval_seam.py tests/test_go_bestmove.py -k "search_root or negamax" -q -x` | ❌ created by this task | ⬜ pending |
| 01-03-T3 | 01-03 | 3 | UCI-06, UCI-07, UCI-09, UCI-10 | T-01-06, T-01-08 | Full `go` grammar parsed-and-ignored where unimplemented (no crash on `wtime`/`btime`); `stop`/`quit` bounded; `ucinewgame` reseeds the tie-break RNG (D-17) | integration (subprocess) | `.venv/bin/python -m pytest tests/test_go_bestmove.py -q -x` | ❌ created by this task | ⬜ pending |
| 01-04-T1 | 01-04 | 4 | EVAL-02 | — | PST tables transcribed from 01-RESEARCH.md's pinned appendix; reference-cell values checked, not just table shape | unit | `.venv/bin/python -m pytest tests/test_eval_seam.py -k pst -q -x` | ❌ created by this task (`tables.py`) | ⬜ pending |
| 01-04-T2 | 01-04 | 4 | EVAL-02 | — | Material+PST subtotal symmetric at startpos; discrete king-table phase switch (not tapered) | unit | `.venv/bin/python -m pytest tests/test_eval_seam.py -k "material_and_pst or king_table" -q -x` | ❌ created by this task (`handcrafted.py`) | ⬜ pending |
| 01-04-T3 | 01-04 | 4 | EVAL-02 | T-01-09, T-01-10 | Mobility/bishop-pair/tempo/pawn-structure terms added; `HandcraftedEval` wired as the live default; `negamax.py` remains evaluator-agnostic | unit + structural | `.venv/bin/python -m pytest tests/test_eval_seam.py -q -x` | ❌ extends 01-04-T1/T2's file | ⬜ pending |
| 01-05-T1 | 01-05 | 5 | TOOL-02 | — | `RandomMover` deterministic per seed; `play_game` always terminates via `max_halfmoves` cap | unit | `.venv/bin/python -m pytest tests/test_random_mover_gauntlet.py -q -m "not slow" -x` | ❌ created by this task | ⬜ pending |
| 01-05-T2 | 01-05 | 5 | TOOL-02 | T-01-11 | 100-game gauntlet bounded by the halfmove cap; `wins == 100` and `losses == 0` required (draws fail) | integration (slow) | `.venv/bin/python -m pytest tests/test_random_mover_gauntlet.py -q -m slow -x` | ❌ extends 01-05-T1's file | ⬜ pending |
| 01-06-T1 | 01-06 | 5 | TOOL-01 | T-01-12 | Human observes a full GUI game with no hang, crash, or disqualification | manual (checkpoint:human-verify) | N/A — blocking human checkpoint | ❌ no file (manual only) | ⬜ pending |

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

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — every `auto` task carries an `<automated>` pytest command; the only tasks without one (`01-01-T1`, `01-06-T1`) are `checkpoint:human-verify` gates, not `auto` tasks
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — the two non-automated tasks (`01-01-T1`, `01-06-T1`) sit at the very start and very end of the 15-task sequence, never adjacent to each other or bunched
- [x] Wave 0 covers all MISSING references — `01-01-T2` stands up `pyproject.toml`/pytest config/venv before any test file is referenced
- [x] No watch-mode flags — every `<automated>` command is a one-shot `pytest ... -q -x` (or `-m slow` / `-m "not slow"`) invocation
- [x] Feedback latency < 5s (quick suite) — per-task commands are narrow `-k`/single-file selections; only the Plan 01-05 `-m slow` gauntlet exceeds 5s, and it is wave-level per Sampling Rate above, not per-commit
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-05
