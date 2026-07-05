# Project Research Summary

**Project:** ANCE — A Neural-network Chess Engine
**Domain:** UCI chess engine (classical alpha-beta search + supervised NNUE evaluation), pure-Python runtime with a separate PyTorch/MPS offline training pipeline on Apple Silicon M4
**Researched:** 2026-07-05
**Confidence:** HIGH

## Executive Summary

ANCE is a UCI-compatible chess engine whose strength comes from a supervised-trained NNUE-style neural evaluation driving a classical alpha-beta search, built in pure Python on a single Apple Silicon M4. This is a decades-stable, well-documented domain: the UCI protocol, alpha-beta search heuristics, and the NNUE training pipeline are all corroborated by authoritative sources (`official-stockfish/nnue-pytorch/docs/nnue.md`, the Chessprogramming Wiki, `python-chess`). Experts build this exact class of engine as **two programs that share one artifact and one contract**: an offline trainer that *produces* a versioned weights file, and an online engine that *consumes* it — with the online engine carrying **zero PyTorch dependency** and reimplementing NNUE inference in numpy.

The recommended approach is uncontroversial and low-risk on technology choice: Python 3.12 (native arm64), `python-chess` for board/movegen only (hand-write the UCI stdin/stdout loop — `chess.engine` is a client, not a server), PyTorch with the MPS backend for training the plain `(768→N)×2→1` net, and Stockfish + Cute Chess for labeling and Elo measurement. The single most important architectural act is fixing the `evaluate(board) -> centipawns` seam (side-to-move relative) in M1 so the NNUE drops in at M3 without touching search, and so a future compiled port is a port, not a rewrite.

The risk is not *what* to build but *getting the details exactly right* — this domain is a minefield of silent correctness bugs. The top risks are: (1) searching on the main thread, which blocks `stop`/stdin and makes the engine "hang" (the #1 M1 killer); (2) the NNUE side-to-move perspective/sign error, which trains to low loss but plays *worse* than the handcrafted baseline (the #1 M3 killer); and (3) TT mate-score-by-ply and bound-flag bugs in M2. Every one of these is silent — nothing errors — so the mitigation is disciplined golden tests and a rigorous ≥1000-game, fixed-opening-book gauntlet to honestly measure the NNUE Elo gain.

## Key Findings

### Recommended Stack

The stack shape has HIGH confidence; only exact pinned versions are MEDIUM (PyTorch/MPS availability regresses across macOS majors — treat `torch.backends.mps.is_available()` as a project-init gate). Detail in STACK.md.

**Core technologies:**
- **Python 3.12 (native arm64)** — engine + trainer language; Rosetta silently disables MPS.
- **python-chess (`chess` 1.11.2)** — board state, legal movegen, FEN/PGN, Zobrist, repetition/50-move; used for the *board*, not UCI I/O.
- **PyTorch 2.x + MPS backend** — trains the NNUE net on the M4 GPU; float32-only (no float64 on MPS), skip AMP/FP16.
- **NumPy 2.x** — feature encoding and the engine-side NNUE forward pass (keeps torch out of the runtime).
- **Stockfish 17.1+** (labeling + gauntlet opponent), **Cute Chess / cutechess-cli** (GUI validation + SPRT/Elo), **lichess-bot** (optional online play).

### Expected Features

FEATURES.md maps every feature to the committed M1→M2→M3 staging. HIGH confidence.

**Must have (table stakes):**
- Non-blocking UCI loop (`uci`/`isready`/`ucinewgame`/`position`/`go`/`stop`/`quit`) that **never hangs** and always returns exactly one `bestmove`.
- Legal movegen + game-end detection via `python-chess`.
- `evaluate(board) -> cp` swap interface with a handcrafted material + PST baseline behind it.
- Negamax alpha-beta + iterative deepening + quiescence (M2).
- Stockfish labeling → dataset → NNUE training → weight export + engine loader (M3).

**Should have (competitive — this is where Elo comes from):**
- Transposition table + hash-move ordering + MVV-LVA + killers/history (M2).
- Real time management (`wtime/btime/winc/binc`) that doesn't flag.
- cutechess-cli self-play gauntlet to measure NNUE vs handcrafted Elo (M3).
- Null-move pruning, tapered eval (M2/M3 strength stretch).

**Defer (v2+ / explicit anti-features):**
- Rust/C++ hot-path port; bucketed/big-net NNUE (HalfKP/HalfKA); MCTS/self-play RL; int8/16 quantization; Syzygy/opening book; LMR/aspiration; multi-threaded SMP; incremental NNUE accumulator (stretch only).

### Architecture Approach

Two decoupled programs joined only by a versioned weights file (`nnue_format/`, imported by both). The online `engine/` never imports torch and reimplements NNUE inference in numpy; the offline `training/` is torch/MPS-only and never ships. Search depends only on an abstract `Evaluator` and a narrow `Position` port surface over `chess.Board`. Detail in ARCHITECTURE.md.

**Major components:**
1. **UCI I/O layer** (main thread) — read stdin, dispatch, spawn/interrupt search via `threading.Event`, emit `info`/`bestmove`.
2. **Board/state layer** — thin `Position` adapter over `chess.Board` (the narrow port surface: push/pop/legal_moves/key/is_draw…).
3. **Search engine** (worker thread) — iterative deepening negamax, TT, quiescence, move ordering, time management; owns `pos.copy()`.
4. **Evaluator seam** — `evaluate(pos) -> int` (cp, stm-relative); `HandcraftedEval` and `NnueEval` behind one contract.
5. **nnue_format** — the shared handoff contract; validates arch_id/feature_set/shapes and fails loudly.
6. **Training pipeline** — Stockfish labeler → dataset shards → PyTorch `(768→N)×2→1` MPS train loop → exporter.

### Critical Pitfalls

Top 5 of 15 documented in PITFALLS.md; each is a silent bug with a concrete detection signal.

1. **Search on the main thread blocks `stop`/stdin (engine "hangs")** — architect reader-thread + search-thread with a polled stop flag from M1; retrofitting is painful. (M1)
2. **NNUE side-to-move perspective/sign error** — trains to low loss but plays *below* the handcrafted baseline. Pin the convention (net output = STM-POV), normalize labels to STM, concatenate `[own, their]`, and run golden symmetry tests. (M3)
3. **TT mate scores not ply-adjusted** — store `score ± ply`, reverse on probe; unit-test with mate-in-2/3 suites for stable `score mate N`. (M2)
4. **TT bound flags (EXACT/LOWER/UPPER) wrong** — only trust an entry for cutoff when `depth >= remaining` and the bound is window-compatible; keep move-ordering benefit separate from score cutoff. (M2)
5. **Eval scale/units mismatch** — train on `sigmoid(cp/K)` win-prob (K≈360–400, measure it), not raw-cp MSE; know Stockfish's normalized UCI cp ≠ internal eval. Plus quiescence explosion, time-loss forfeits, MPS float64/fallback/OOM, and Elo measured with too few games. (M3)

## Implications for Roadmap

Research strongly endorses the committed M1→M2→M3 staging and supplies a dependency-honoring build order. Suggested phases:

### Phase 1: Minimal UCI Engine (M1)
**Rationale:** UCI plumbing de-risks the interface first with fast GUI feedback, and the threading model must exist from day one (retrofitting it after search is painful). This is pure I/O concurrency, not chess strength.
**Delivers:** Non-blocking UCI loop; `position` reset-and-replay; legal movegen + game-end via `python-chess`; the `evaluate(board)->cp` seam with a handcrafted material+PST eval; a random/first-legal `bestmove`. Validated in Cute Chess, beats a random mover 100/100.
**Addresses:** UCI protocol surface, eval swap interface, handcrafted baseline (FEATURES.md table stakes).
**Avoids:** Main-thread search hang; missing stdout flush / missing `bestmove`; `position ... moves` state corruption.

### Phase 2: Strong Alpha-Beta Search (M2)
**Rationale:** With plumbing proven, build the guaranteed-working fallback engine the Core Value demands *before* any ML risk. Move ordering is the multiplier — stage TT + killers/history before any reductions/pruning.
**Delivers:** Iterative-deepening negamax + quiescence; transposition table (bound+depth, ply-adjusted mate scores); MVV-LVA + hash-move + killer/history ordering; real time management (soft/hard limits); full `info` output; repetition/50-move draw detection; the cutechess-cli gauntlet harness + opening book.
**Uses:** `python-chess` Zobrist; `chess.engine` to drive Stockfish/Cute Chess (STACK.md).
**Implements:** Search engine + TT + timeman components (ARCHITECTURE.md).
**Avoids:** TT mate-score/bound bugs, quiescence explosion, checkmate/stalemate sign errors, time-loss forfeits.

### Phase 3: First Supervised NNUE (M3)
**Rationale:** NNUE arrives last as a *swap* behind the existing seam, not a rewrite. Training is decoupled (binds only via `nnue_format/`) so it can start in parallel after Phase 1.
**Delivers:** Stockfish labeling pipeline → dataset with game-level train/val split + FEN dedup → `(768→N)×2→1` PyTorch/MPS training → weight export → numpy `NnueEval` (full recompute) behind the seam → parity check → ≥1000-game cutechess-cli gauntlet confirming measurable Elo gain. Optional lichess-bot deployment.
**Uses:** PyTorch MPS, numpy inference, Stockfish labels (STACK.md).
**Avoids:** NNUE perspective/sign error, eval scale/units mismatch, data leakage, MPS float64/fallback/OOM, under-powered Elo measurement.

### Phase Ordering Rationale
- **Dependencies:** UCI seam → search core → eval swap is the discovered dependency chain. The eval interface must exist in M1 for the M3 swap to be a swap. Quiescence must precede trusting any eval; TT + ordering must precede any pruning/reductions.
- **Risk sequencing:** A working swappable-eval alpha-beta engine (end of M2) is the milestone's guaranteed fallback per Core Value, delivered before ML risk enters.
- **Parallelism:** The training pipeline shares only `nnue_format/` and can be developed alongside M1/M2.
- **Measurement backbone:** The gauntlet + opening-book harness is built in M2 and used decisively in M3.

### Research Flags

Phases likely needing deeper research (`--research-phase`) during planning:
- **Phase 3 (M3):** Highest research need — NNUE feature construction/perspective, the sigmoid-WDL loss + scaling constant K, quantization semantics (even if deferred), and MPS numeric validation are all detail-critical and easy to get silently wrong. Re-verify `torch.backends.mps.is_available()` on the actual installed macOS/PyTorch before committing.

Phases with standard, well-documented patterns (can skip research-phase):
- **Phase 1 (M1):** UCI protocol is a canonical, decades-stable spec; `python-chess` usage is well-documented.
- **Phase 2 (M2):** Alpha-beta, TT, quiescence, and move ordering are established prior art on the Chessprogramming Wiki — implement carefully against the pitfall checklist rather than researching anew.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core shape verified against primary docs; exact PyTorch version MEDIUM (verify MPS availability on target macOS at init). |
| Features | HIGH | Domain is decades-stable; UCI spec + NNUE pipeline corroborated by authoritative sources. |
| Architecture | HIGH | Two-program split + Evaluator/Position seams are well-established prior art, verified against nnue-pytorch and python-chess. |
| Pitfalls | HIGH | Corroborated against nnue-pytorch docs, Stockfish wiki, PyTorch MPS tracker, UCI conventions; MEDIUM only on exact macOS-version thresholds. |

**Overall confidence:** HIGH

### Gaps to Address
- **PyTorch/MPS on the installed macOS:** MPS `is_available()` has regressed on new macOS majors (Tahoe/2.9–2.10). Make a smoke test the first task of the training harness; CPU training is a viable fallback for this tiny net.
- **WDL scaling constant K:** ~360–400 is a starting point tied to SF-scaled data — measure against the actual labels rather than hardcoding. Handle during M3 planning.
- **Stockfish labeling convention:** Normalized UCI cp ≠ internal eval (SF12+); document the exact SF command (eval vs search score, depth, normalization) before generating the dataset.
- **Elo measurement discipline:** ≥1000 games + fixed opening book + one-thing-at-a-time (swap only eval) is required for any Elo claim to survive a rerun.

## Sources

### Primary (HIGH confidence)
- `official-stockfish/nnue-pytorch` — `docs/nnue.md`: two-perspective/STM feature construction, ClippedReLU, quantization scales (127/64), sigmoid-WDL training target, 768 vs HalfKP feature sets.
- `niklasf/python-chess` docs (v1.11.2) — legal movegen, `push`/`pop`/`move_stack`, FEN parsing, repetition/50-move detection, Zobrist hashing, `chess.engine`.
- Chessprogramming Wiki — alpha-beta, iterative deepening, quiescence, TT bound flags, MVV-LVA, killers/history, null-move, LMR.
- Stockfish "Normalize evaluation" commit + wiki — normalized UCI cp ≠ internal value since SF12+; WDL scaling ~360–400.

### Secondary (MEDIUM confidence)
- developer.apple.com/metal/pytorch + PyTorch MPS notes — MPS requirements, float64/fallback caveats.
- cutechess/lichess-bot/Stockfish/Lc0 release pages — tool versions and platform notes.
- database.lichess.org — zstd PGN dumps, ~6% with SF-NNUE `[%eval]` tags.

### Tertiary (LOW confidence — validate locally)
- pytorch/pytorch issues #167679, #177819 — MPS-unavailable-on-macOS-26 regression (verify on installed macOS/PyTorch).
- jw1912/bullet Metal backend — newer path, not stress-tested; reserved for a later scale-up milestone.

---
*Research completed: 2026-07-05*
*Ready for roadmap: yes*
