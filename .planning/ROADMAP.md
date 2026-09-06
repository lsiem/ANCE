# Roadmap: ANCE — A Neural-network Chess Engine

## Overview

ANCE is delivered as five vertical slices that follow the discovered dependency
chain **UCI seam → search core → search strength → offline training → NNUE swap-in**.
Phase 1 stands up a non-blocking UCI engine with the `evaluate()` seam and a
handcrafted eval — enough to play a full legal game in a GUI and beat a random
mover. Phases 2–3 turn that into a genuinely strong, clock-safe alpha-beta engine
(the milestone's guaranteed fallback per Core Value) and build the gauntlet
measurement backbone. Phase 4 runs offline (it binds only to the shared weights
contract, so it can proceed in parallel once the eval seam exists) and produces a
validated, exported NNUE. Phase 5 is the payoff: the trained net drops in behind
the untouched search seam and is proven to beat the handcrafted baseline over a
rigorous ≥1000-game gauntlet. Phase 6 closes the strength gap when TOOL-04 fails
honestly: quiet, result-bearing training data + Stockfish-aligned trainer recipe.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Minimal UCI Engine & Evaluator Seam** - Non-blocking UCI loop, handcrafted eval behind the swap seam, plays a full legal game (validated live in En Croissant) and never loses to a random mover (0 losses, ≥70% wins — replanned 2026-07-07) (completed 2026-07-08)
- [x] **Phase 2: Core Alpha-Beta Search** - Iterative-deepening negamax + quiescence + draw detection with full `info` output — plays real, tactically sound chess (completed 2026-07-08)
- [x] **Phase 3: Search Acceleration & Time Management** - Transposition table, full move ordering, real clock control, and the self-play gauntlet harness (completed 2026-07-11)
- [x] **Phase 4: Offline NNUE Training Pipeline** - Stockfish labeling → game-split dataset → PyTorch/MPS `(768→N)×2→1` training → validated exported weights (completed 2026-07-18)
- [ ] **Phase 5: NNUE Swap-In & Elo Gauntlet** - numpy NnueEval behind the seam, parity + perspective tests, and a ≥1000-game gauntlet proving measurable Elo gain — 05-03 evidence written; gates_failed (honest)
- [ ] **Phase 6: Quiet-Data NNUE Strength Gap** - Quiet/result-bearing corpus, λ schedule + fen-skipping, Elo-probe checkpoints, 200→1000 re-gate (no HalfKA) — 06-06 evidence written; gates_failed (honest)

## Phase Details

### Phase 1: Minimal UCI Engine & Evaluator Seam

**Goal**: A GUI-playable UCI engine that never hangs, routes every leaf through a swappable `evaluate(position)->cp` seam, and plays a full legal game with a handcrafted eval.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: UCI-01, UCI-02, UCI-03, UCI-04, UCI-05, UCI-06, UCI-07, UCI-09, UCI-10, UCI-12, SRCH-01, EVAL-01, EVAL-02, TOOL-01, TOOL-02
**Success Criteria** (what must be TRUE):

  1. In Cute Chess / Arena the engine completes the `uci`/`isready` handshake and plays a full legal game to a natural result without hanging or being disqualified.
  2. A piped `position … / go / stop` script always returns exactly one legal `bestmove` promptly — even mid-search and in mate/stalemate/zero-legal-move positions (stdout flushed on every line).
  3. The engine beats a random-mover opponent 100 games out of 100.
  4. Swapping the evaluator behind the `evaluate(position)->cp` seam (side-to-move relative) changes only the eval — no search-side change is required.
  5. `position fen <malformed>` is rejected without crashing, and `ucinewgame` resets per-game state cleanly.

**Plans**: 4/6 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Walking Skeleton: ance package, python -m ance entry point, non-blocking uci/isready/quit handshake, trivial first-legal-move bestmove, pytest subprocess harness

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Position adapter: position startpos/fen/moves, malformed-input rejection (D-10), ucinewgame reset, terminal detection (SRCH-01), stderr debug channel (D-18)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Evaluator seam (Evaluator Protocol) + fixed-depth negamax substrate; full go depth/movetime/infinite/stop/quit handling with tie-break RNG and bestmove (none)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — Full handcrafted evaluator: Simplified Evaluation Function PSTs + king mg/eg tables + mobility/bishop-pair/tempo/pawn-structure terms, wired in as the default eval

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-05-PLAN.md — Random-mover self-play gauntlet proving ANCE wins 100 games out of 100
- [x] 01-06-PLAN.md — Manual GUI validation checkpoint (Cute Chess/Arena full game, TOOL-01)

### Phase 2: Core Alpha-Beta Search

**Goal**: The engine plays real, tactically sound chess via iterative-deepening fail-soft negamax with quiescence and correct draw/terminal handling, reporting its thinking each iteration.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: SRCH-02, SRCH-03, SRCH-04, SRCH-07, UCI-11
**Success Criteria** (what must be TRUE):

  1. The engine searches with fail-soft negamax alpha-beta and iterative deepening, always keeping and returning the best move from the last completed depth when interrupted.
  2. Quiescence search resolves captures/promotions so the engine stops hanging pieces to the horizon effect (node counts stay bounded in tactical positions).
  3. During search the engine emits `info depth <d> score cp <x>|mate <y> nodes <n> nps <n> pv <moves>` each iteration, with `pv[0]` matching `bestmove`.
  4. The engine detects threefold repetition and the 50-move rule inside search and does not repeat or draw a won position.
  5. Terminal nodes score correctly (checkmate = −(MATE−ply), stalemate = 0, negamax sign correct) and deeper search never plays measurably worse.

**Plans**: 12/12 plans complete

Plans:

- [x] 02-11-PLAN.md
- [x] 02-12-PLAN.md

- [x] 02-07-PLAN.md
- [x] 02-08-PLAN.md
- [x] 02-09-PLAN.md
- [x] 02-10-PLAN.md

**Wave 1**

- [x] 02-01-PLAN.md — Fail-soft alpha-beta negamax, ply-adjusted mate scoring, SearchResult types, deterministic root (SRCH-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Quiescence search: captures + queen promos, stand-pat + delta pruning, MVV-LVA in qsearch only (SRCH-04)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-03-PLAN.md — Iterative deepening, twofold/50-move/insufficient-material draw detection (SRCH-03, SRCH-07)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-04-PLAN.md — UCI info lines per completed depth, bare-go movetime budget, go infinite until stop (UCI-11)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 02-05-PLAN.md — Tactical/mate-in-N tests, folded depth-4 gauntlet, depth-vs-depth strength proof (D-01, D-13, D-14)

**Wave 6** *(gap closure — UAT test 4)*

- [x] 02-06-PLAN.md — Mate scores on the wire in signed full moves + eval cp clamp below mate window (D-18, UCI-11 gap closure)

### Phase 3: Search Acceleration & Time Management

**Goal**: A strong, clock-safe engine — Zobrist transposition table, full move ordering, and real time management — plus a reusable self-play gauntlet harness to measure eval changes honestly.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SRCH-05, SRCH-06, SRCH-08, UCI-08, TOOL-03
**Success Criteria** (what must be TRUE):

  1. A Zobrist-keyed transposition table stores correct EXACT/LOWER/UPPER bounds with ply-adjusted mate scores; fixed-depth search is reproducible and mate-in-2/3 report a stable `score mate N` across depths.
  2. Move ordering (hash move → MVV-LVA → killers → history) measurably increases cutoffs / reaches greater depth than the Phase 2 baseline at equal time.
  3. Under `go wtime/btime/winc/binc` the engine computes a per-move budget and never loses on time across a 100-game blitz gauntlet (soft + hard limits; `movetime`/`depth`/`infinite` honored).
  4. `ucinewgame` clears the transposition table so state never leaks across games.
  5. A `cutechess-cli` gauntlet harness runs two identical-search builds from a fixed opening book and reports a score with error bars (validated handcrafted-vs-handcrafted ≈ 50%).

**Plans**: 0/6 plans executed

**Wave 1** *(parallel — baseline + harness before search changes)*

- [x] 03-01-PLAN.md — Phase 2 baseline snapshot (D-20/D-21 yardstick before TT/ordering)
- [x] 03-02-PLAN.md — Self-play gauntlet harness: arbiter clocks, openings, Wilson CI (TOOL-03)

**Wave 2**

- [x] 03-03-PLAN.md — Zobrist transposition table, mate ply, ucinewgame clear (SRCH-05)

**Wave 3**

- [x] 03-04-PLAN.md — Full move ordering + D-21 baseline comparison (SRCH-06)

**Wave 4**

- [x] 03-05-PLAN.md — Clock budgeting wtime/btime/winc/binc (SRCH-08, UCI-08)

**Wave 5**

- [x] 03-06-PLAN.md — 100-game blitz evidence: zero forfeits + 50% sanity (D-14, D-17)

### Phase 4: Offline NNUE Training Pipeline

**Goal**: An offline PyTorch/MPS pipeline turns Stockfish-labeled positions into a validated, exported `(768→N)×2→1` weights file the engine can load — binding to the engine only through the shared `nnue_format` contract.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: TRN-01, TRN-02, TRN-03, TRN-04, TRN-05
**Success Criteria** (what must be TRUE):

  1. A Stockfish labeling pipeline produces (FEN → centipawn) samples at a fixed depth/nodes using normalized UCI cp, with the exact labeling command recorded.
  2. The dataset is deduplicated by FEN and split train/val by game (not by position), with an automated check that no FEN appears in both splits.
  3. The `(768→N)×2→1` net trains in PyTorch on the MPS backend against a sigmoid-scaled win-probability target, with a decreasing, trustworthy validation loss.
  4. Training first verifies `torch.backends.mps.is_available()` and passes a float32 CPU-vs-MPS numeric sanity check before the real run.
  5. Trained weights export to a plain versioned format (npz/safetensors) that the shared loader validates (arch id / feature-set / shapes) and roundtrips with zero torch dependency.

**Plans**: 7/7 plans complete

Plans:

**Wave 1**

- [x] 04-01-PLAN.md — Environment setup (torch/numpy/safetensors/zstandard/scipy/tqdm + Stockfish), `nnue_format` contract (D-07/TRN-04), MPS gate (D-09/TRN-05)

**Wave 2** *(parallel — no file overlap, all depend only on Wave 1)*

- [x] 04-02-PLAN.md — NNUE model (D-06), sigmoid-WDL training loop, export path — thin end-to-end slice on synthetic data (TRN-03/TRN-04/TRN-05)
- [x] 04-03-PLAN.md — Fresh Stockfish labeling + depth benchmark + provenance manifest (TRN-01/D-02)
- [x] 04-04-PLAN.md — Lichess ingestion with sign correction, merge/dedup, by-game split with disjointness assertion (TRN-02/D-01/D-03)
- [x] 04-05-PLAN.md — K-fit calibration (D-04/D-05) + 768-index feature encoder

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 04-06-PLAN.md — On-disk shards, real DataLoader-driven training with checkpointing, full mechanical pipeline smoke test

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-07-PLAN.md — Pipeline CLI orchestrator + the real ~8-12h bounded training run (D-08, checkpoint:human-verify)

### Phase 5: NNUE Swap-In & Elo Gauntlet

**Goal**: The trained NNUE drops in behind the untouched evaluator seam and is proven to beat the handcrafted baseline over a rigorous gauntlet — the milestone's defining payoff.
**Mode:** mvp
**Depends on**: Phase 3, Phase 4
**Requirements**: EVAL-03, TOOL-04
**Success Criteria** (what must be TRUE):

  1. A numpy `NnueEval` (full recompute, zero torch) implements the same `evaluate(position)->cp` seam, loads the exported weights, and passes a parity check against the torch forward pass on held-out FENs.
  2. Golden perspective/sign tests pass: symmetric positions evaluate to ≈ 0, a color-mirror-with-STM-flip gives equal scores, and net eval sign/magnitude match Stockfish on sample FENs.
  3. Swapping handcrafted → NNUE changes only the eval; the two gauntlet builds are diff-verified to share identical search configuration.
  4. Over a ≥1000-game fixed-opening-book `cutechess-cli` gauntlet the NNUE build shows a measurable positive Elo gain over the handcrafted build, reported with error bars (CI/SPRT) and reproducible on a rerun.

**Plans**: 2/3 plans executed

Plans:

**Wave 1**

- [x] 05-01-PLAN.md — NnueEval + git-tracked `net.safetensors` + `ANCE_EVAL` wiring + torch↔numpy parity/golden tests (EVAL-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — Gauntlet `--depth` + `EngineSpec.env` + logistic Elo/Wilson CI + search-config diff verify (TOOL-04 harness)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 05-03-PLAN.md — ≥1000-game depth-3 evidence run + D-12 Elo CI gate + committed evidence JSON (TOOL-04 proof) — evidence written; gates_failed (honest)

### Phase 6: Quiet-Data NNUE Strength Gap

**Goal**: Rebuild the training distribution around quiet, result-bearing positions and Stockfish-aligned trainer controls so NNUE can pass TOOL-04 (`elo_ci_low > 0`) at fixed depth 3.
**Mode:** mvp
**Depends on**: Phase 5 (honest evidence)
**Requirements**: TOOL-04 (re-gate), TRN data/quality
**Success Criteria** (what must be TRUE):

  1. Strength corpus prefers Lichess PGN + HF fill; fresh random-walk ≤10%; ≥50% rows have `game_result`; K is fitted (not fallback-only).
  2. Quiet filter rejects checks, capture-bestmoves, and `|static − qsearch| > 60`; training cp soft-clamped to ±10000.
  3. Trainer supports λ 1.0→0.75, random fen-skipping 3, resume-from, and mid-train Elo probes; final net is best-by-Elo when probes ran.
  4. Diagnostics pass; 200-game probe gate then ≥1000-game TOOL-04; accumulator parity + optional clock/nodes note. No HalfKA.

**Plans**: 6/6 executed (measurement failed honestly)

Plans:

- [x] 06-01 — Quiet filter + mate clamp + corpus mix guards + tests
- [x] 06-02 — λ schedule, fen-skip, resume-from CLI
- [x] 06-03 — Mid-train Elo probes + best_elo export + dashboard
- [x] 06-04 — Diagnostics + 200→1000 closer + dual TC evidence (harness)
- [x] 06-05 — Accumulator parity / nps evidence (no arch change)

**Wave 1** *(measurement)*

- [x] 06-06-PLAN.md — Quiet-data net diagnostics → 200-game probe → ≥1000 TOOL-04 evidence — probe 0–200; gates_failed (honest)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 (Phase 4 may proceed in parallel with 2–3; Phase 5 requires both 3 and 4; Phase 6 follows honest Phase 5 evidence).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Minimal UCI Engine & Evaluator Seam | 6/6 | Complete    | 2026-07-08 |
| 2. Core Alpha-Beta Search | 12/12 | Complete    | 2026-07-10 |
| 3. Search Acceleration & Time Management | 6/6 | Complete    | 2026-07-11 |
| 4. Offline NNUE Training Pipeline | 7/7 | Complete    | 2026-07-18 |
| 5. NNUE Swap-In & Elo Gauntlet | 2/3 | Gap (D-12 failed) | 2026-07-20 |
| 6. Quiet-Data NNUE Strength Gap | 6/6 | Gap (D-12 failed) | 2026-09-06 |
