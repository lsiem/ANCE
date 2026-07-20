# Gap Plan Draft: Phase 05 D-12 Elo Gate (pending final evidence)

**Status:** Draft — finalize after clean 1000-game gauntlet completes  
**Created:** 2026-07-20  
**Trigger:** HF-primary net projected to fail D-12 (early clean score 0–N, Elo −∞)

## Problem

NNUE (HF-trained ~37k unique positions) loses consistently to handcrafted at fixed depth 3 under identical search. Milestone TOOL-04 / D-12 requires Elo > 0 and `elo_ci_low` > 0 over ≥1000 games.

## Likely causes

1. **Data scale / quality** — 250k HF rows collapse to ~37k unique FENs; mate/extreme cp density; no game-result WDL mix (`K=400` fallback).
2. **Sign / target issues** — HF net mis-scores material-winning positions (e.g. rook-up white-to-move ≈ −380 cp vs handcrafted ≈ +200). Labels look STM-correlated in aggregate, but net polarity on tactics is unreliable.
3. **Capacity** — plain `(768→256)×2→1` may need more diverse supervised data (or SF depth-12 scale labels) before it can beat a tuned handcrafted eval at depth 3.

## Proposed follow-ups (pick after evidence lands)

1. **Resume Mac SF 1M depth-12 labeling** from local progress JSON (original scale-run path).
2. **Larger HF stream** with mate filtering + `|cp|` clip before shard build; verify rook-up / startpos goldens before gauntlet.
3. **Blend streams** — Lichess PGN `[%eval]` (result-bearing for K-fit) + HF + fresh SF.
4. **Optional** — temporarily raise acceptance depth only after a smoke ≥20-game score_rate > 0.45 (does not change D-10 game count).

## Non-goals

- Changing search to bail out NNUE
- Claiming TOOL-04 with <1000 games
