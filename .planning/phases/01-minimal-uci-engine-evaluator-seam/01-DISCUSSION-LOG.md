# Phase 1: Minimal UCI Engine & Evaluator Seam - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-05
**Phase:** 1-minimal-uci-engine-evaluator-seam
**Areas discussed:** Move selection, Handcrafted eval, Identity & options, Robustness/errors, Threading & stop, Launch & entry point, `go infinite`, Debug logging

---

## Move selection

### Search substrate
| Option | Description | Selected |
|--------|-------------|----------|
| Minimal fixed-depth negamax | No pruning/quiescence/ID; honors `go depth`/`movetime`; Phase 2 skeleton | ✓ |
| 1-ply greedy only | Simplest; but `go depth N>1` is a no-op; Phase 2 rebuilds search | |

### Bare `go` behavior
| Option | Description | Selected |
|--------|-------------|----------|
| Fixed default depth | Deterministic, testable, always terminates; movetime aborts to root-best | ✓ |
| Short default movetime | GUI-like but nondeterministic and harder to unit-test | |

### Tie-breaking
| Option | Description | Selected |
|--------|-------------|----------|
| Random among equal-best | Seedable; avoids shuffle loops; varies games vs random mover | ✓ |
| Deterministic first-best | Fully reproducible but robotic/repetitive play | |

**User's choice:** Minimal fixed-depth negamax; bare `go` → fixed default depth; random-among-equal-best (seeded in tests).
**Notes:** UCI-07 requiring `go depth` in Phase 1 drove the negamax-over-greedy choice — the substrate isn't scope creep, it's what UCI-07 needs. `movetime`/`stop` return best root move found so far.

---

## Handcrafted eval

### PST basis
| Option | Description | Selected |
|--------|-------------|----------|
| Simplified Evaluation Function | Michniewski values + single-phase PSTs + king mid/end tables; canonical, verifiable | ✓ |
| Plain hand-picked PSTs | Simpler self-authored tables, fewer to transcribe | |

### Extra terms
| Option | Description | Selected |
|--------|-------------|----------|
| Pure material + PST | Deliberately-weak minimal baseline | |
| Add cheap terms | Slightly stronger baseline, more to test | ✓ |

### Which terms (multi-select)
| Option | Description | Selected |
|--------|-------------|----------|
| Mobility | Legal-move-count difference; costs a movegen call per leaf | ✓ |
| Bishop pair | Flat ~30–50cp bonus; trivial | ✓ |
| Tempo | ~10cp bonus for side to move | ✓ |
| Pawn structure | Doubled + isolated pawn penalties | ✓ |

**User's choice:** Simplified Evaluation Function + all four cheap terms (mobility, bishop pair, tempo, pawn structure).
**Notes:** User consciously chose a richer baseline over the minimal one despite the recommendation, accepting that it raises the bar for the Phase 5 NNUE Elo-gain proof (deemed a more honest baseline). Mobility's per-leaf movegen cost flagged for later optimization.

---

## Identity & options

### id name / author
| Option | Description | Selected |
|--------|-------------|----------|
| ANCE + version, Lasse | `id name ANCE 0.1` (build-distinguishable in logs), `id author Lasse Siemoneit` | ✓ |
| ANCE, no version | Simpler but builds indistinguishable in gauntlet/GUI logs | |

### UCI options surface
| Option | Description | Selected |
|--------|-------------|----------|
| Declare none | id + uciok only; `setoption` ignored gracefully | ✓ |
| Placeholder Hash option | Cosmetic no-op Hash slider; arguably misleading pre-TT | |

**User's choice:** `id name ANCE 0.1` / `id author Lasse Siemoneit`; declare zero options; ignore `setoption`.
**Notes:** Version in name chosen specifically to distinguish handcrafted vs NNUE builds in Phase 5 gauntlet logs.

---

## Robustness/errors

### Malformed FEN / illegal move
| Option | Description | Selected |
|--------|-------------|----------|
| Reject, keep board | Leave current board untouched + `info string`; standard, recovers cleanly | ✓ |
| Reject, reset to startpos | Predictable but can silently mask a GUI/position mismatch | |

### Zero-legal-move `go`
| Option | Description | Selected |
|--------|-------------|----------|
| bestmove (none) | Stockfish convention; matches SF in gauntlet log diffs | ✓ |
| bestmove 0000 | Formal UCI null-move token; less self-documenting | |

**User's choice:** Reject bad FEN + keep board + `info string`; terminal `go` → `bestmove (none)`.
**Notes:** Unknown-command handling delegated to Claude → silently ignore per UCI spec.

---

## Threading & stop

| Option | Description | Selected |
|--------|-------------|----------|
| Cancel flag, polled periodically | `threading.Event` + deadline, checked every ~1–2k nodes and at each root move | ✓ |
| Check on every node | Maximally prompt but per-node overhead, costly in pure Python | |

**User's choice:** Cancel flag polled periodically; `quit` sets flag then exits after worker unwinds.
**Notes:** stdout flushed per line to keep handshake/bestmove unbuffered.

---

## Launch & entry point

| Option | Description | Selected |
|--------|-------------|----------|
| python -m ance | `ance/` package + `__main__.py`; modular; no install step | ✓ |
| Console script | pyproject entry point; cleanest invocation but needs editable install | |
| Single main.py | Simplest but fights the modular/swappable-eval structure | |

**User's choice:** `python -m ance` package layout.
**Notes:** GUI/gauntlet command = arm64 venv python + `-m ance`.

---

## `go infinite`

| Option | Description | Selected |
|--------|-------------|----------|
| Search, then idle until stop | Search to default depth, hold result, emit bestmove only on `stop`; UCI-correct | ✓ |
| Treat as default go | Simpler but violates UCI (infinite must wait for stop) | |

**User's choice:** Search to default depth then idle until `stop`.
**Notes:** Reader stays non-blocking throughout so `stop`/`quit` always accepted.

---

## Debug logging

| Option | Description | Selected |
|--------|-------------|----------|
| stderr, toggled by debug | stderr-only, off by default, toggled by UCI `debug on/off` / `ANCE_DEBUG` | ✓ |
| No debug channel in M1 | Only `info string`; harder to diagnose silent hangs | |

**User's choice:** stderr debug channel toggled by `debug on/off`.
**Notes:** Never write diagnostics to stdout — keeps the protocol stream clean.

---

## Claude's Discretion

- Exact default search depth value (tune to pure-Python speed).
- Internal module/file names and the precise node-count polling interval.
- Whether the debug channel also honors an `ANCE_DEBUG` env var alongside UCI `debug on/off`.
- Precise `info string` wording for rejected input.
- Unknown/unsupported command handling → silently ignore per UCI spec.

## Deferred Ideas

- `setoption` / configurable Hash/net-path/threads — v2 (CFG-01).
- Tapered (midgame/endgame) evaluation — v2 (EVAL-04).
- Console-script (`ance`) entry point via pyproject — revisit at packaging time.
- Caching/incremental mobility to avoid per-leaf movegen cost — when real search arrives.
