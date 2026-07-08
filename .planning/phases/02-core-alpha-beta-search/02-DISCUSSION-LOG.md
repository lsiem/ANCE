# Phase 2: Core Alpha-Beta Search - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 02-Core Alpha-Beta Search
**Areas discussed:** Todo folding, Quiescence design, Draw handling in search, ID behavior & info output, Strength validation

---

## Todo folding

| Option | Description | Selected |
|--------|-------------|----------|
| Fold it in (Recommended) | Include deferred TOOL-02 depth-4 gauntlet in Phase 2 validation | ✓ |
| Keep deferred | Leave todo in backlog for a later phase | |

**User's choice:** Fold it in
**Notes:** Original 100/0 @ depth-4 target deferred from Phase 1 due to unpruned search cost; alpha-beta makes it practical now.

---

## Quiescence design

| Option | Description | Selected |
|--------|-------------|----------|
| Captures + queen promotions (Recommended) | Quiet-node qsearch examines captures and queen promotions | ✓ |
| Captures, promotions + checks | Broader qsearch move set | |
| Captures only | Minimal qsearch | |

| Option | Description | Selected |
|--------|-------------|----------|
| Stand-pat + delta pruning (Recommended) | Bound qsearch node count | ✓ |
| Stand-pat only | Simpler but more nodes | |
| You decide | Delegate to planner | |

| Option | Description | Selected |
|--------|-------------|----------|
| MVV-LVA inside qsearch only (Recommended) | Order captures in qsearch; main search unordered for Phase 3 baseline | ✓ |
| No ordering anywhere | Fully unordered | |
| MVV-LVA in qsearch AND main search captures | Pre-empts Phase 3 ordering work | |

| Option | Description | Selected |
|--------|-------------|----------|
| Search all evasions, no stand-pat (Recommended) | In-check nodes: all evasions, zero evasions = mate | ✓ |
| Stand-pat anyway, captures only | | |
| You decide | | |

**User's choice:** Captures + queen promotions; stand-pat + delta; MVV-LVA in qsearch only; all evasions when in check.

---

## Draw handling in search

| Option | Description | Selected |
|--------|-------------|----------|
| Twofold-in-search = draw (Recommended) | Game history or search-path repetition scores 0 | ✓ |
| Strict threefold only | | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Plain 0 (Recommended) | No contempt factor | ✓ |
| Small contempt (~ -15 cp) | | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes - both, python-chess helpers (Recommended) | 50-move + insufficient material via helpers | ✓ |
| 50-move only, skip insufficient material | | |
| You decide | | |

**User's choice:** Twofold-in-search draw; plain 0; both 50-move and insufficient material.

---

## ID behavior & info output

| Option | Description | Selected |
|--------|-------------|----------|
| Default movetime budget (Recommended) | ~2s soft budget for bare `go` | ✓ |
| Raise the fixed default depth | | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Drop it - deterministic PV (Recommended) | Remove Phase 1 D-04 RNG tie-break | ✓ |
| Keep RNG at final root iteration only | | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| One line per completed depth (Recommended) | Single info line per finished ID iteration | ✓ |
| Per depth + periodic node updates | | |
| You decide | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Deepen until stop (Recommended) | `go infinite` iterates until stop/MAX_PLY | ✓ |
| Keep Phase 1 idle behavior | | |
| You decide | | |

**User's choice:** Default movetime ~2s; drop RNG; one info line per depth; infinite deepens until stop.

---

## Strength validation

| Option | Description | Selected |
|--------|-------------|----------|
| Mate-in-N + tactical pytest suite (Recommended) | Fixed FEN tactical tests beyond gauntlet | ✓ |
| Gauntlet only | | |
| Suite + a WAC subset benchmark | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Depth-vs-depth self-play mini-match (Recommended) | ~30-50 games, deeper side ≥ 50% | ✓ |
| Tactical-suite monotonicity only | | |
| Both | | |

| Option | Description | Selected |
|--------|-------------|----------|
| <= 10 minutes (Recommended) | Wall-clock budget for depth-4 gauntlet | ✓ |
| <= 5 minutes | | |
| No hard budget | | |

| Option | Description | Selected |
|--------|-------------|----------|
| Escalate depth, then judge (Recommended) | Depth 5 if depth 4 cap-draws; pass on losses==0 + improved win-rate | ✓ |
| Hard requirement - 100/0 or phase fails | | |
| Raise max_halfmoves cap too | | |

**User's choice:** Tactical suite + depth-vs-depth mini-match; ≤10 min gauntlet budget; escalate-then-judge fallback.

---

## Claude's Discretion

- MAX_PLY cap for infinite search
- Exact default movetime constant
- Qsearch depth/extension internals

## Deferred Ideas

- v1.1 local web-app GUI (existing backlog todo, not folded)
- Strict 100/0 @ depth 4 may remain Phase 3 target if cap-draws persist
