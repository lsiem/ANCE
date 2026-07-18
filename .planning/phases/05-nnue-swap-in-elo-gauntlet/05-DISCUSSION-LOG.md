# Phase 5: NNUE Swap-In & Elo Gauntlet - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 5-NNUE Swap-In & Elo Gauntlet
**Areas discussed:** Eval switch / two-build wiring, Weights path contract, Elo gauntlet protocol (TOOL-04), Parity & golden acceptance bar

---

## Eval switch / two-build wiring

### Q1 — How should the two builds select their evaluator?

| Option | Description | Selected |
|--------|-------------|----------|
| Env var | `ANCE_EVAL=handcrafted\|nnue`; works with cutechess/arbiter | ✓ |
| CLI flag | `python -m ance --eval nnue` | |
| UCI setoption | GUI-friendly; more gauntlet moving parts | |

**User's choice:** Env var

### Q2 — Default when `ANCE_EVAL` unset?

| Option | Description | Selected |
|--------|-------------|----------|
| Default handcrafted | NNUE only when explicitly set | ✓ |
| Default NNUE once wired | Handcrafted opt-in | |
| You decide | | |

**User's choice:** Default handcrafted

### Q3 — Unknown `ANCE_EVAL` value?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast | Non-zero exit, list allowed values | ✓ |
| Warn + fall back to handcrafted | Silent wrong-eval risk | |
| You decide | | |

**User's choice:** Fail fast

### Q4 — Enforce identical search config?

| Option | Description | Selected |
|--------|-------------|----------|
| Same argv; only env differs | Matches Phase 3 EngineSpec | ✓ |
| Two tiny entry modules | Hardcoded eval per module | |
| You decide | | |

**User's choice:** Same argv; env only

---

## Weights path contract

### Q1 — Default weights location?

| Option | Description | Selected |
|--------|-------------|----------|
| Env + package default | `ANCE_NNUE_PATH` else baked-in path | ✓ |
| Env-only required | No default | |
| Cwd discovery | Fragile across launchers | |

**User's choice:** Env + package default

### Q2 — Missing / invalid weights when NNUE selected?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast at startup | No silent handcrafted fallback | ✓ |
| Warn + fall back | | |
| You decide | | |

**User's choice:** Fail fast

### Q3 — Ship Phase 4 net as package default?

| Option | Description | Selected |
|--------|-------------|----------|
| Copy into ance/ and track in git | ~790 KB, reproducible | ✓ |
| Copy but gitignore | | |
| You decide | | |

**User's choice:** Copy + track in git

### Q4 — Load-time metadata strictness?

| Option | Description | Selected |
|--------|-------------|----------|
| Strict schema match | arch_id / feature_set / shapes | ✓ |
| Shapes only | | |
| You decide | | |

**User's choice:** Strict

---

## Elo gauntlet protocol (TOOL-04)

### Q1 — Completion-valid runner?

| Option | Description | Selected |
|--------|-------------|----------|
| D-15 cutechess-or-arbiter | Don't block on missing cutechess | ✓ |
| cutechess required | | |
| Arbiter-only | | |

**User's choice:** Keep D-15

### Q2 — Stop rule?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed ≥1000 games | Report Elo + 95% CI | ✓ |
| SPRT first | | |
| You decide | | |

**User's choice:** Fixed ≥1000

### Q3 — Time control?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed depth both sides | Clean eval-only comparison | ✓ |
| Blitz clocks | | |
| You decide | | |

**User's choice:** Fixed depth

### Q4 — Measurable positive Elo?

| Option | Description | Selected |
|--------|-------------|----------|
| Point > 0 and 95% CI lower bound > 0 | | ✓ |
| Point estimate > 0 only | | |
| Minimum Elo floor | | |

**User's choice:** CI lower bound > 0

---

## Parity & golden acceptance bar

### Q1 — Torch ↔ numpy parity?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact after shared float→int | | ✓ |
| Loose abs tolerance | | |
| You decide | | |

**User's choice:** Exact

### Q2 — Symmetric ≈ 0?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact 0 | | ✓ |
| Within a few cp | | |
| You decide | | |

**User's choice:** Exact 0

### Q3 — Color-mirror + STM-flip?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact equality | | ✓ |
| Within 1 cp | | |
| You decide | | |

**User's choice:** Exact equality

### Q4 — Stockfish sample FENs?

| Option | Description | Selected |
|--------|-------------|----------|
| Sign agreement on small won/lost suite | | ✓ |
| Strict magnitude correlation | | |
| Skip SF comparison | | |

**User's choice:** Sign agreement suite

---

## Claude's Discretion

- Package-relative path for baked-in net
- Concrete FEN suites for parity / goldens / SF-sign
- Fixed depth N and opening book for overnight ≥1000 games
- Elo/CI formula details meeting D-12
- Automated diff-verify of identical search config

## Deferred Ideas

None new. Reviewed but not folded: TOOL-02 depth-4 backlog, v1.1 GUI, Phase 2 En Croissant todo.
