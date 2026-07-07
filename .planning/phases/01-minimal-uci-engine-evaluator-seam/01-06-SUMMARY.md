---
phase: 01-minimal-uci-engine-evaluator-seam
plan: 06
subsystem: testing
tags: [uci, arbiter, cutechess, python-chess, validation, tool-01]

requires:
  - phase: 01-minimal-uci-engine-evaluator-seam
    provides: "python -m ance UCI entry point, non-blocking loop, handcrafted eval, stop/preemption"
provides:
  - "Human-delegated external-arbiter validation of TOOL-01: ANCE plays full legal games to natural results over real UCI"
affects: []

tech-stack:
  added: []
  patterns:
    - "External UCI arbiter validation via python-chess chess.engine (ANCE-vs-ANCE), the project's sanctioned tool for driving external engines / gauntlets"

key-files:
  created: []
  modified: []

key-decisions:
  - "No macOS Cute Chess binary exists (v1.5.1 ships win64 + Linux AppImage only; none of the last 20 releases has a mac asset; no brew formula/cask) — validated TOOL-01 with an equivalent external UCI arbiter instead of the Cute Chess GUI window"
  - "Used python-chess chess.engine to drive two independent `python -m ance` processes over real UCI pipes — same stdin/stdout boundary a GUI uses"

patterns-established:
  - "TOOL-01 acceptance via a real external arbiter (full game, real clock, no DQ/hang) rather than only in-process self-play (01-05) or subprocess unit tests"

requirements-completed: [TOOL-01]

coverage:
  - id: D1
    description: "ANCE completes the UCI handshake and plays a full legal game to a natural result over a real external arbiter, without hanging, crashing, illegal move, or disqualification — validated ANCE-vs-ANCE via python-chess chess.engine (two independent UCI subprocesses)"
    requirement: "TOOL-01"
    verification:
      - kind: integration
        ref: "scratchpad/uci_arbiter_game.py Game 2 (go movetime 500) — 108 plies, 0-1 CHECKMATE, slowest move 0.60s, no illegal/hang/crash"
        status: pass
      - kind: manual_procedural
        ref: "CLI smoke: printf 'uci\\nisready\\nposition startpos\\ngo depth 3\\nquit' | .venv/bin/python -m ance -> uciok/readyok/bestmove g1h3, exit 0"
        status: pass
    human_judgment: true
    rationale: "TOOL-01 was scoped as human observation in a real GUI (Cute Chess/Arena). No macOS Cute Chess build exists, so the literal GUI-window observation was substituted by an equivalent external UCI arbiter (python-chess driving ANCE-vs-ANCE). Substance (handshake, full legal game, natural result, real clock, no DQ/hang) is met with concrete passing evidence; the literal human-eyes-on-GUI step remains optional and open. User (the human) delegated this checkpoint and accepted the arbiter evidence."
  - id: D2
    description: "ANCE completes a full legal game under a real clock time control (engine receives `go wtime/btime/winc/binc`), confirming Plan 01-03's parsed-but-ignored clock params never cause an arbiter timeout in Phase 1"
    requirement: "TOOL-01"
    verification:
      - kind: integration
        ref: "scratchpad/uci_arbiter_game.py Game 1 (5+2 clock, chess.engine.Limit white_clock/black_clock/white_inc/black_inc) — 48 plies, 1/2-1/2 THREEFOLD_REPETITION, no timeout/DQ"
        status: pass
    human_judgment: true
    rationale: "Same GUI-substitution rationale as D1. Note: Game 1's slowest single move was 7.26s (pure-Python depth-3 in a busy middlegame). Fine at 5+2, but on a very fast time control a real arbiter could eventually flag ANCE on time because Phase 1 parses but does not act on the clock — real clock budgeting is Phase 3 (UCI-08), explicitly out of scope here."

duration: ~40min
completed: 2026-07-07
status: complete
---

# Phase 01 / Plan 06: Manual GUI Validation Gate (TOOL-01) Summary

**TOOL-01 validated via a real external UCI arbiter (ANCE-vs-ANCE over python-chess): two full legal games to natural results (a checkmate and a threefold-repetition draw), real clock + movetime, no hang / illegal move / disqualification — Cute Chess GUI substituted because no macOS build exists.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-07-07T19:25:30Z
- **Tasks:** 1 (checkpoint:human-verify, delegated by the user and executed via arbiter)
- **Files modified:** 0 (validation-only gate)

## Accomplishments

- Confirmed the exact GUI entry point (`<repo>/.venv/bin/python -m ance`) does a clean `uci`→`uciok`, `isready`→`readyok`, and returns a legal `bestmove` (CLI smoke test).
- Played **two full legal games** ANCE-vs-ANCE through a real external UCI arbiter (python-chess `chess.engine`, two independent subprocesses over stdin/stdout):
  - **Game 1 — real clock** (`go wtime/btime/winc/binc`, 5+2): 48 plies → ½–½ threefold repetition. No timeout/DQ. (plan step d)
  - **Game 2 — `go movetime 500`**: 108 plies → 0–1 checkmate. Slowest move 0.60s.
- Verified `go infinite` → `stop` yields **exactly one** `bestmove` (clean preemption, no stale/duplicate output — plan step e equivalent), and malformed FEN is rejected without crashing then a subsequent `go` returns a legal move (CLI).
- Full pytest suite (the automated backbone this gate complements) green: **52 passed**.

## Files Created/Modified

- None (validation gate). Throwaway arbiter harness lives in the session scratchpad: `scratchpad/uci_arbiter_game.py`.

## Decisions Made

- **Cute Chess is not installable on macOS.** Release v1.5.1 ships only `win64` and a Linux `x86_64.AppImage`; no macOS asset exists in the last 20 releases, and Homebrew has no formula/cask. Building from source needs the Qt 6.8 + cmake toolchain — a heavy detour not implied by "install Cute Chess."
- **Substituted an equivalent external UCI arbiter.** Per CLAUDE.md, `chess.engine` is the sanctioned tool for *driving* external engines (gauntlets). Driving ANCE-vs-ANCE over real UCI pipes with a real clock exercises the same stdin/stdout boundary and rule/timeout enforcement a GUI arbiter would, and produced concrete, reproducible passing evidence.

## Deviations from Plan

- **Method substitution (accepted):** TOOL-01 was scoped as human observation in the Cute Chess/Arena GUI. Because no macOS Cute Chess binary exists, the literal GUI-window game was replaced with a functionally equivalent external UCI arbiter game. The must-haves' *substance* (handshake, full legal game to natural result, real clock, no DQ/hang) is genuinely met; the literal human-eyes-on-a-GUI observation remains optional/open and is recorded as `human_judgment: true` in the coverage block.

## Issues Encountered

- **Fast time-control caveat (deferred to Phase 3):** Game 1's slowest single move was 7.26s (pure-Python fixed-depth-3 in a dense middlegame). Harmless at 5+2, but on a very fast control a strict arbiter could eventually flag ANCE on time, since Phase 1 parses but does not act on the clock. Real clock budgeting is Phase 3 (UCI-08) — expected and in-scope for later, not a Phase 1 defect.

## Next Phase Readiness

- Phase 1's Core-Value deliverable is proven end-to-end over real UCI: the engine plays complete legal games to natural results through an external arbiter with a swappable handcrafted eval, never hanging or being disqualified.
- Optional follow-up (does not block Phase 2): a literal human GUI game in a macOS-available GUI (e.g. BanksiaGUI) or a from-source Cute Chess / fastchess arbiter, if human-eyes-on-GUI confirmation is desired.
- Ready for **Phase 2: Core Alpha-Beta Search** (iterative-deepening negamax + quiescence + full `info` output).

---
*Phase: 01-minimal-uci-engine-evaluator-seam*
*Completed: 2026-07-07*
