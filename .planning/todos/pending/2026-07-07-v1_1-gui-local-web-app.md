---
created: 2026-07-07T18:38:48Z
title: "v1.1 milestone: local web-app GUI showing live evaluation, games, and search metrics"
area: gui
files: []
resolves_phase: null
milestone: v1.1
---

## Problem

ANCE v1.0 is designed to plug into *existing* GUIs (Cute Chess / Arena) — a
custom GUI is deliberately out of v1.0 scope (PROJECT.md "Validated in a GUI"
requirement points at existing tools, and none of the five v1.0 roadmap phases
build a GUI). The user wants a dedicated GUI that visualizes what the engine is
doing: current evaluation, the games being played, and search metrics.

Requested via `/gsd-plan-phase "add a GUI support for UCI protocol where the
user can see evaluation, the games and metrics"` on 2026-07-07. Because it is
new scope beyond v1.0's Core Value (NNUE strength), the user chose to slot it
as a **new milestone (v1.1)** rather than a v1.0 phase.

## Locked decisions (from /gsd-plan-phase questioning, 2026-07-07)

- **Milestone placement:** v1.1 (post-v1.0). Not a v1.0 phase. Kick off only
  after v1.0 ships (`/gsd-complete-milestone` → `/gsd-new-milestone`).
- **GUI form:** **Local web app** — a Python backend (e.g. FastAPI/Flask +
  WebSocket) drives the ANCE engine over UCI; a browser UI renders the board,
  an evaluation bar/curve, the live game, and streaming search metrics.
  (Desktop app and TUI were the considered alternatives; web app was chosen.)

## Scope sketch (to refine in discuss-phase when v1.1 is kicked off)

The GUI is a **consumer** of engine output. Its headline features depend on
engine capabilities that land during v1.0:

- **Live search metrics** (`info depth <d> score cp <x>|mate <y> nodes <n>
  nps <n> pv <moves>`) first appear in **Phase 2 (Core Alpha-Beta Search)**.
  A metrics GUI has little to show until Phase 2 is done — a key reason it was
  deferred to v1.1 rather than built now.
- **Evaluation display** becomes far more meaningful once the **NNUE eval**
  (Phase 5) is in, though the handcrafted eval (Phase 1) already produces a
  side-to-move-relative cp score to visualize.

Likely v1.1 phase shape (illustrative, not committed):
1. Backend service that spawns/drives ANCE over UCI, parses `info`/`bestmove`,
   and streams structured state to clients (WebSocket).
2. Browser UI: board rendering, move list, eval bar/graph, live info panel
   (depth/score/nodes/nps/pv), and game controls (new game, play vs engine,
   engine-vs-engine, load FEN/PGN).
3. Metrics/history view: per-move eval curve, nps/depth over time.

Open questions for discuss-phase:
- Play modes: human-vs-ANCE, ANCE-vs-ANCE, analysis-only?
- Does it reuse the existing `python -m ance` UCI process, or embed the engine
  in-process?
- Web stack specifics (FastAPI vs Flask; frontend framework vs vanilla).
- Does it belong before or after a lichess-bot deployment?

## Solution

When v1.0 is complete:
1. `/gsd-complete-milestone` to archive v1.0.
2. `/gsd-new-milestone` for v1.1 — carry the two locked decisions above into
   requirements, then roadmap the GUI phases, then `/gsd-plan-phase`.
3. Sequence the GUI so its metrics features build on the Phase 2 `info` output
   that already exists by then.
