---
created: 2026-07-08T18:15:00Z
title: "Phase 2 must close with a watched En Croissant validation game (D-19) — no plan schedules it"
area: tooling
files:
  - .planning/phases/02-core-alpha-beta-search/02-CONTEXT.md
resolves_phase: 2
---

## Problem

Phase 2 round-2 discussion locked D-19 (see `02-CONTEXT.md` addendum): the
phase closes with a **watched En Croissant validation game**, mirroring Phase
1's dedicated 01-06 GUI checkpoint plan. The user validates by watching, not
by reading logs (established preference from Phase 1 / TOOL-01).

Plans 02-01 … 02-05 were created before this decision was captured; none of
them schedules a manual GUI checkpoint. 02-04 fixes `go infinite` ("Unlimited")
in code but nothing verifies it live.

## Solution

Before Phase 2 verification / UAT completes, run a manual GUI checkpoint
(either as an additional plan 02-06 or as part of `/gsd-verify-work` UAT):

1. Load ANCE (arm64 venv `python -m ance`) in En Croissant.
2. Play/watch a full ANCE-vs-ANCE game at a **fixed time-per-move** preset;
   confirm live `info depth/score/pv` lines render in the GUI and the game
   reaches a natural result.
3. Separately confirm the "Unlimited" mode fix: `go infinite` now visibly
   deepens (info lines updating) and `stop` produces a bestmove — the Phase 1
   "Unlimited hangs ANCE" note in PROJECT.md Key Decisions can then be updated.
4. Record the outcome in the phase UAT/verification artifacts.
