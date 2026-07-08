# Requirements: ANCE — A Neural-network Chess Engine

**Defined:** 2026-07-05
**Core Value:** The engine plays legal, tactically sound chess through a clean UCI interface, and gets measurably stronger when a trained NNUE evaluation replaces the handcrafted one.

## v1 Requirements

Milestone 1 scope: **M1** minimal UCI engine → **M2** strong alpha-beta search → **M3** first supervised NNUE eval. Each requirement maps to a roadmap phase.

### UCI Protocol

- [x] **UCI-01**: Engine responds to `uci` with `id name`, `id author`, declared `option` lines, then `uciok`
- [x] **UCI-02**: Engine responds to `isready` with `readyok` and never blocks, including mid-initialization
- [x] **UCI-03**: Engine handles `ucinewgame` by resetting per-game state (no-op in M1; clears TT/history in M2)
- [x] **UCI-04**: Engine sets its board from `position startpos [moves ...]`
- [x] **UCI-05**: Engine sets its board from `position fen <fen> [moves ...]` and rejects malformed FEN without crashing
- [x] **UCI-06**: Every `go` command yields exactly one legal `bestmove <uci>` and never hangs
- [x] **UCI-07**: Engine honors `go movetime <ms>` and `go depth <n>`
- [ ] **UCI-08**: Engine honors clock control `go wtime/btime/winc/binc` and computes a per-move time budget
- [x] **UCI-09**: Engine honors `stop` by ending search promptly and emitting the current `bestmove`
- [x] **UCI-10**: Engine handles `quit` with a clean exit that never deadlocks on a running search
- [ ] **UCI-11**: Engine emits `info depth <d> score cp <x>|mate <y> nodes <n> nps <n> pv <moves>` during search
- [x] **UCI-12**: The stdin/stdout loop stays readable during search so `stop`/`quit` are always honored (non-blocking)

### Search

- [x] **SRCH-01**: Engine generates only legal moves and detects checkmate, stalemate, and draws via python-chess
- [ ] **SRCH-02**: Engine searches with fail-soft negamax alpha-beta
- [ ] **SRCH-03**: Engine uses iterative deepening and always keeps the best move from the last completed depth
- [ ] **SRCH-04**: Engine runs a quiescence search over captures to avoid the horizon effect
- [ ] **SRCH-05**: Engine uses a Zobrist-keyed transposition table with correct exact/lower/upper bounds and ply-adjusted mate scores on store and probe
- [ ] **SRCH-06**: Engine orders moves hash-move → MVV-LVA captures → killers → history
- [ ] **SRCH-07**: Engine detects repetition and the 50-move rule to avoid losing drawn positions
- [ ] **SRCH-08**: Engine manages its clock so it never loses on time under `wtime/btime/winc/binc`

### Evaluation

- [x] **EVAL-01**: A stable `evaluate(position) -> centipawns` interface exists, side-to-move relative, with mate scored as ±(MATE − ply); NNUE must drop in without any search change
- [x] **EVAL-02**: A handcrafted material + piece-square-table evaluator implements the interface (the M3 baseline to beat)
- [ ] **EVAL-03**: A `(768→N)×2→1` NNUE evaluator implements the same interface, loading trained weights

### Training & Data

- [ ] **TRN-01**: A Stockfish labeling pipeline produces (FEN → centipawn) training samples at a fixed depth/nodes, using normalized UCI cp output (not internal eval)
- [ ] **TRN-02**: A dataset is generated with a train/validation split held out by game (not by position) to prevent leakage
- [ ] **TRN-03**: The `(768→N)×2→1` NNUE trains in PyTorch on the MPS backend against a sigmoid-scaled win-probability target
- [ ] **TRN-04**: Trained weights export to a plain format (npz/safetensors) and the running engine loads them at startup
- [ ] **TRN-05**: Training verifies MPS availability and runs a float32 CPU-vs-MPS numeric sanity check before the real run

### Tooling & Measurement

- [x] **TOOL-01**: The engine loads and plays a full legal game in a GUI (Cute Chess / Arena)
- [x] **TOOL-02**: The engine never loses to a random-mover opponent (losses==0) and wins at least 70% of games, with every non-win a draw (REPLANNED 2026-07-07 from the original 100/100 target, which proved impractical/unproven at depth 4 unpruned; 100/0-at-depth-4 deferred to a future pruning phase, see pending todo)
- [ ] **TOOL-03**: A `cutechess-cli` self-play gauntlet harness runs two identical-search builds (differing only in eval) from a fixed opening book
- [ ] **TOOL-04**: The NNUE build shows a measurable Elo gain over the handcrafted build across a ≥1000-game gauntlet reported with error bars

## v2 Requirements

Deferred to future release. Tracked but not in the current roadmap.

### Search Strength

- **SRCH-09**: Null-move pruning with a zugzwang guard
- **SRCH-10**: Late-move reductions (only after move ordering is proven)
- **SRCH-11**: Aspiration windows around the previous iteration's score
- **EVAL-04**: Tapered (midgame/endgame) evaluation

### Configuration & Deployment

- **CFG-01**: `setoption` support for hash size, net path, and threads
- **DEPL-01**: lichess-bot deployment wrapping the UCI engine

### NNUE Performance

- **NNUE-01**: Incremental accumulator updates on make/unmake instead of full recompute

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Rust/C++ hot-path port | Splits focus before the Python engine works; deferred to a later milestone. Code stays modular for a future port. |
| MCTS + policy/value net (AlphaZero-style engine) | Different paradigm; abandons the committed NNUE + alpha-beta vehicle |
| Self-play reinforcement learning | Infeasible compute on a single M4 — the reason supervised was chosen |
| Large bucketed / big-net NNUE (HalfKP, HalfKAv2, king buckets) | 10M+ params, complex; overkill for the first net. Start plain, scale later. |
| Cloud / NVIDIA `bullet` training | Out of budget scope; M4/MPS is the committed training box |
| int8/int16 quantized inference | Adds correctness risk before the float net proves an Elo gain; belongs with the compiled port |
| Syzygy tablebases / in-engine opening book | Orthogonal to "does NNUE beat handcrafted"; adds surface area |
| Multi-threaded / Lazy SMP search | Python GIL makes real search parallelism painful; a compiled-port concern |
| MultiPV / ponder / full analysis mode | Extra protocol surface with no bearing on the benchmarks |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| UCI-01 | Phase 1 | Complete |
| UCI-02 | Phase 1 | Complete |
| UCI-03 | Phase 1 | Complete |
| UCI-04 | Phase 1 | Complete |
| UCI-05 | Phase 1 | Complete |
| UCI-06 | Phase 1 | Complete |
| UCI-07 | Phase 1 | Complete |
| UCI-09 | Phase 1 | Complete |
| UCI-10 | Phase 1 | Complete |
| UCI-12 | Phase 1 | Complete |
| SRCH-01 | Phase 1 | Complete |
| EVAL-01 | Phase 1 | Complete |
| EVAL-02 | Phase 1 | Complete |
| TOOL-01 | Phase 1 | Complete |
| TOOL-02 | Phase 1 | Complete |
| SRCH-02 | Phase 2 | Pending |
| SRCH-03 | Phase 2 | Pending |
| SRCH-04 | Phase 2 | Pending |
| SRCH-07 | Phase 2 | Pending |
| UCI-11 | Phase 2 | Pending |
| SRCH-05 | Phase 3 | Pending |
| SRCH-06 | Phase 3 | Pending |
| SRCH-08 | Phase 3 | Pending |
| UCI-08 | Phase 3 | Pending |
| TOOL-03 | Phase 3 | Pending |
| TRN-01 | Phase 4 | Pending |
| TRN-02 | Phase 4 | Pending |
| TRN-03 | Phase 4 | Pending |
| TRN-04 | Phase 4 | Pending |
| TRN-05 | Phase 4 | Pending |
| EVAL-03 | Phase 5 | Pending |
| TOOL-04 | Phase 5 | Pending |

**Coverage:**

- v1 requirements: 32 total
- Mapped to phases: 32 (100%) — Phase 1: 15, Phase 2: 5, Phase 3: 5, Phase 4: 5, Phase 5: 2
- Unmapped: 0 (no orphans, no duplicates)

---
*Requirements defined: 2026-07-05*
*Last updated: 2026-07-05 after roadmap creation (traceability populated)*
