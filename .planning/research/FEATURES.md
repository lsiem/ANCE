# Feature Research

**Domain:** UCI chess engine — NNUE evaluation + alpha-beta search (Python, Apple Silicon M4)
**Researched:** 2026-07-05
**Confidence:** HIGH (domain is decades-stable; UCI spec, alpha-beta heuristics, and NNUE pipeline corroborated by official-stockfish/nnue-pytorch docs, backscattering.de UCI spec, and Chessprogramming Wiki)

> **Milestone framing.** This document maps every feature to the committed staging:
> **M1** = minimal UCI engine that plays legal games and never hangs on `go`.
> **M2** = strong iterative-deepening alpha-beta (TT + quiescence + move ordering + time management).
> **M3** = first supervised NNUE wired as the leaf eval, with measurable Elo gain over the handcrafted eval.
> Anything past M3 (Rust/C++ port, bucketed/big-net NNUE, self-play RL, MCTS) is an **anti-feature** this milestone.

---

## Feature Landscape

### Table Stakes (Engine is broken / unplayable without these)

These are non-negotiable. Missing any one means the engine fails a GUI handshake, hangs, or plays illegal moves.

#### (a) UCI protocol surface

| Feature | Why Expected | Complexity | Milestone | Notes |
|---------|--------------|------------|-----------|-------|
| `uci` → `id name`/`id author` + `uciok` | Handshake; GUI refuses engine without it | LOW | M1 | Emit any declared `option` lines here too |
| `isready` → `readyok` | Required before searching + as keepalive ping | LOW | M1 | Must respond even mid-init; never block forever |
| `ucinewgame` | Signals new game; reset per-game state (TT, history) | LOW | M1 | Safe to treat as a no-op in M1, clears TT in M2 |
| `position startpos [moves ...]` | Sets internal board from start + move list | LOW | M1 | `python-chess`: `Board()` then `board.push(Move.from_uci(m))` |
| `position fen <fen> [moves ...]` | Sets arbitrary position; GUIs use it constantly | LOW | M1 | `Board(fen)`; validate FEN, reject malformed input |
| `go` → always returns `bestmove <uci>` | The core contract; every `go` MUST yield a bestmove | MEDIUM | M1 | Even a random/first-legal move in M1 satisfies the contract |
| `go movetime <ms>` | Fixed think time; simplest reliable time control | LOW | M1 | Hard stop by wall clock |
| `go depth <n>` | Fixed-depth search; used for testing/labeling | LOW | M1→M2 | Trivial once iterative deepening exists |
| `go wtime/btime/winc/binc` | Real clock control used by every GUI + lichess-bot | MEDIUM | M2 | Needs a time-budget policy (see time management) |
| `go nodes <n>` | Node-limited search; useful for reproducible tests | LOW | M2 | Requires a node counter in search |
| `stop` → prompt `bestmove` | GUI must be able to interrupt; else engine hangs | MEDIUM | M1→M2 | Needs cooperative cancellation flag checked in search loop |
| `quit` | Clean process exit | LOW | M1 | Flush and exit; don't deadlock on a running search |
| `info depth <d> score cp <x> nodes <n> nps <n> pv <moves>` | GUI shows thinking; without it engine looks dead/broken | MEDIUM | M1(min)→M2(full) | `score mate <y>` when forced mate detected |
| stdin/stdout loop that never blocks the reader | If reading blocks during search, `stop`/`quit` never arrive → hang | HIGH | M1 | **Highest-risk table stake.** Search must run so input is still readable (thread or periodic poll). This is the "never hangs on `go`" benchmark. |

#### (b) Search — minimum to produce a legal, non-embarrassing move

| Feature | Why Expected | Complexity | Milestone | Notes |
|---------|--------------|------------|-----------|-------|
| Legal move generation | Illegal move = instant loss / GUI rejection | LOW | M1 | Delegate to `python-chess` `board.legal_moves`; do NOT hand-roll |
| Negamax alpha-beta | Baseline of every classical engine | MEDIUM | M2 | Fail-soft negamax; the spine everything else hangs off |
| Iterative deepening | Enables anytime `stop`, gives move ordering seed | MEDIUM | M2 | Search depth 1,2,3…; keep best move from last completed depth |
| Quiescence search | Without it, eval is garbage at horizon (hangs pieces) | MEDIUM | M2 | Search captures (+ checks optionally) until quiet; prevents horizon effect |
| Checkmate/stalemate/draw handling | Must recognize game end and score ±mate / 0 | LOW | M1 | `python-chess`: `is_checkmate`, `is_stalemate`, `is_insufficient_material` |
| Repetition + 50-move draw detection | Avoids losing drawn positions / illegal claims | LOW | M2 | `board.is_repetition()`, `board.can_claim_fifty_moves()` |
| Basic time management | Must not flag (lose on time) or waste the clock | MEDIUM | M2 | Simple `remaining/moves_to_go + increment` budget; check clock between iterations |

#### (c) Evaluation — swappable module

| Feature | Why Expected | Complexity | Milestone | Notes |
|---------|--------------|------------|-----------|-------|
| Stable `evaluate(board) -> centipawns` interface | The swap boundary; NNUE must drop in without touching search | LOW | M1 | **Design this early.** Side-to-move-relative sign convention fixed here. |
| Handcrafted material eval | Baseline so the engine plays *something* sane | LOW | M1 | Standard piece values (P=100…Q=900) |
| Piece-square tables (PST) | Gives positional sense; the M3 Elo baseline to beat | LOW | M1→M2 | Tapered (midgame/endgame) optional; a single PST set is fine to start |

#### (d) Training / data — to produce the M3 net

| Feature | Why Expected | Complexity | Milestone | Notes |
|---------|--------------|------------|-----------|-------|
| Stockfish labeling pipeline | Generates the (position → eval) training signal | MEDIUM | M3 | Local Stockfish at fixed depth/nodes; store FEN + cp score |
| Position source / dataset generation | Need diverse positions (self-play or PGN corpora) | MEDIUM | M3 | Random-ply openings + Stockfish play, or public PGN; dedup positions |
| Dataset format + train/val split | Reproducible training; honest validation | LOW | M3 | Simple: FEN,score CSV/npz → tensors. Hold out a val set by game, not by position (avoid leakage) |
| NNUE `(768→N)×2→1` model in PyTorch (MPS) | The committed architecture | MEDIUM | M3 | 768 = 64×6×2 features per perspective (side-to-move + opponent), no king buckets |
| Training loop (loss on sigmoid-scaled eval) | Converts labels into weights | MEDIUM | M3 | Loss blends eval (cp→win-prob via sigmoid) and optionally WDL via a lambda |
| Weight export + engine loader | Net must be loadable by the running engine | MEDIUM | M3 | Export to a plain format (npz/safetensors); engine loads at startup / via `setoption` |
| NNUE wired as leaf eval behind the eval interface | The payoff — NNUE replaces handcrafted at the leaves | MEDIUM | M3 | Same `evaluate()` signature; no search changes |

#### (e) Tooling — validation & strength measurement

| Feature | Why Expected | Complexity | Milestone | Notes |
|---------|--------------|------------|-----------|-------|
| Runs in a GUI (Cute Chess / Arena) | Human-playable validation; catches protocol bugs | LOW | M1 | Register the engine binary/launcher; play a full game |
| Beats a random mover 100/100 | The M1 correctness gate | LOW | M1 | Automatable via Cute Chess CLI |
| Self-play gauntlet for Elo (Cute Chess CLI) | The only honest measure of "did NNUE help?" | MEDIUM | M3 | `cutechess-cli` tournament, handcrafted-eval build vs NNUE build, N games, SPRT/Elo report |
| lichess-bot deployment | Real-world games vs varied opponents | MEDIUM | M3 (opt) | `lichess-bot` wraps the UCI engine; nice-to-have, not on the strength critical path |

---

### Differentiators (Add real playing strength — the "strong" in M2, and search-depth multiplier in M3)

Not required to be legal/playable, but this is where Elo comes from.

| Feature | Value Proposition | Complexity | Milestone | Notes |
|---------|-------------------|------------|-----------|-------|
| Transposition table (TT) | Avoids re-searching transpositions; enables PV & move ordering; biggest single search speedup | MEDIUM | M2 | Zobrist-keyed dict/array; store depth, flag (exact/lower/upper), score, best move. `python-chess` provides a Zobrist hash. |
| Hash-move ordering (from TT) | Search the previously best move first → far more cutoffs | LOW | M2 | Depends on TT. Cheapest large gain in alpha-beta. |
| MVV-LVA capture ordering | Orders captures by value gained; improves quiescence + main search | LOW | M2 | Most-Valuable-Victim / Least-Valuable-Attacker; committed in roadmap |
| Killer-move heuristic | Orders quiet moves that caused cutoffs at same ply | LOW-MED | M2 | Two killers per ply; cheap, meaningful ordering gain |
| History heuristic | Global quiet-move ordering from cutoff frequency | MEDIUM | M2 | Complements killers; feeds LMR reduction decisions |
| Null-move pruning | Skips a turn to prove a beta cutoff cheaply; big node reduction | MEDIUM | M2/M3 | Needs zugzwang guard (disable in low-material endgames); depends on quiescence + a working eval |
| Late-move reductions (LMR) | Reduces depth of unlikely (late-ordered) moves; large effective-depth gain | MEDIUM-HIGH | M3+ | **Depends on good move ordering (TT + killers + history) first** — LMR on bad ordering loses Elo |
| Aspiration windows | Narrow alpha-beta window around last score; more cutoffs | MEDIUM | M3+ | Pairs with iterative deepening; needs re-search on fail |
| Tapered eval / phase interpolation | Smooths midgame↔endgame PST; strengthens handcrafted baseline | LOW-MED | M2 (opt) | Makes the handcrafted baseline harder to beat — set the bar honestly |
| Incremental NNUE accumulator updates | The "efficiently updatable" trick: update on make/unmake instead of full recompute; recovers much of the nps NNUE costs | HIGH | M3+ (stretch) | Non-trivial in Python; a from-scratch full-recompute NNUE is the honest M3 target, incremental is a strength/perf stretch |
| `setoption` (Hash size, net path, threads) | Configurable TT size / net swap at runtime; expected of "real" engines | LOW-MED | M2/M3 | Declare matching `option` lines in `uci` output |
| `ponder` (think on opponent's time) | Standard strong-engine feature; extra effective time | MEDIUM | out (M3+) | Declared in question as optional; not on this milestone's critical path |

---

### Anti-Features (Deliberately NOT built this milestone)

| Feature | Why Requested | Why Problematic (this milestone) | Alternative |
|---------|---------------|----------------------------------|-------------|
| Rust/C++ hot-path port | Pure-Python search is orders of magnitude slower | Splits focus before the Python engine even works; premature optimization | Keep search+eval modular so a later milestone can port them; accept the Python nps ceiling now |
| MCTS + policy/value net (AlphaZero-style engine) | "Lc0 is strong" | Different paradigm entirely; abandons the committed NNUE+alpha-beta vehicle; large infra | NNUE + alpha-beta is the strength vehicle; do not run MCTS even as a parallel track |
| Self-play reinforcement learning | "That's how AlphaZero learned" | Infeasible compute on a single M4; the whole reason supervised was chosen | Supervised pretraining on Stockfish labels |
| Large bucketed / big-net NNUE (HalfKP, HalfKAv2, king-buckets, 8-bucket output) | Stockfish's real nets are much stronger | 10M+ params, complex feature transforms, harder to train/quantize on M4; overkill for first net | Plain `(768→N)×2→1` PSQ-style net; scale features/buckets in a later milestone |
| Cloud / NVIDIA `bullet` training | Faster, bigger training | Out of budget scope; M4/MPS is the committed training box | PyTorch MPS on the M4; small batches |
| int8/16 quantization of the net for inference | Stockfish ships quantized `.nnue` | Adds correctness risk + tooling before the float net even proves an Elo gain | Run the float32 net directly in Python for M3; quantize only if/when a compiled port needs it |
| Opening book / endgame tablebases (Syzygy) | GUIs support them; strong engines use them | Orthogonal to the "does NNUE beat handcrafted" question; adds deps + surface area | Play from the board; add later if strength plateaus |
| Multi-threaded / Lazy SMP search | More nps | Python GIL makes real search parallelism painful; huge complexity for this stage | Single-threaded search; parallelism is a compiled-port concern |
| `MultiPV`, full analysis-mode output | Nice for analysis GUIs | Extra protocol surface with no bearing on playing strength or the benchmarks | Single-PV `info` is sufficient for GUI play and gauntlets |

---

## Feature Dependencies

```
UCI stdin/stdout loop (non-blocking)
    └──enables──> stop / quit during search   [the "never hangs" contract]

evaluate(board)->cp  interface  (design in M1)
    ├──impl 1──> handcrafted material + PST   (M1/M2)
    └──impl 2──> NNUE leaf eval               (M3)   [swap, no search change]

negamax alpha-beta
    └──requires──> iterative deepening
                       ├──requires──> quiescence search   (for sane leaf scores)
                       └──enables───> anytime stop / time management

transposition table (TT)
    ├──enables──> hash-move ordering
    └──requires──> Zobrist hashing (python-chess provides)

move ordering (hash move > MVV-LVA > killers > history)
    └──required-before──> late-move reductions (LMR)     [LMR on bad ordering LOSES Elo]
    └──required-before──> null-move pruning              [ordering makes the cheap cutoffs land]

Stockfish labeling pipeline
    └──produces──> dataset (FEN + cp)
                       └──requires──> train/val split (split by GAME, not position)
                                          └──feeds──> NNUE training loop (PyTorch MPS)
                                                          └──produces──> exported weights
                                                                             └──loaded-by──> NNUE leaf eval

self-play gauntlet (cutechess-cli)
    └──requires──> two runnable engine builds (handcrafted-eval vs NNUE-eval)
    └──measures──> Elo gain   [the M3 success benchmark]
```

### Dependency Notes

- **The eval interface must exist before anything else in eval.** Fixing the `evaluate(board) -> centipawns` signature and sign convention in M1 is the single most important architectural act — it is what lets the NNUE drop in at M3 without touching search, and what makes a later compiled port tractable.
- **TT before hash-move ordering; ordering before LMR/null-move.** Move ordering is the multiplier that makes alpha-beta cut. Reductions/pruning applied on top of *bad* ordering actively lose strength, so stage them after TT + killers + history are in and measured.
- **Quiescence before trusting any eval.** Without quiescence, the leaf eval is measured mid-capture and the engine hangs material (horizon effect). This gates both the handcrafted baseline and the NNUE net being judged fairly.
- **Non-blocking I/O loop gates the entire M1 benchmark.** "Plays legal games and never hangs on `go`" is fundamentally an I/O-concurrency requirement, not a chess requirement. Getting `stop`/`quit` to be honored while a search runs is the riskiest M1 item.
- **Split train/val by game, not by position.** Positions from the same game are highly correlated; a naive per-position split leaks and inflates validation numbers, hiding overfitting before the gauntlet exposes it.
- **The gauntlet needs two comparable builds.** Measuring "NNUE vs handcrafted" honestly means identical search, only the eval swapped, run over enough games (SPRT or fixed-N with error bars) via `cutechess-cli`.

---

## MVP Definition

### Launch With — M1 (minimal UCI engine)

- [ ] Non-blocking UCI loop: `uci`, `isready`, `ucinewgame`, `position startpos/fen [moves]`, `go`, `stop`, `quit` — **never hangs**
- [ ] Legal move generation + game-end detection via `python-chess`
- [ ] `go movetime`/`depth` returns a legal `bestmove` every time
- [ ] Minimal `info` line (at least `depth`, `score cp`, `pv`)
- [ ] `evaluate(board) -> cp` interface with handcrafted material (+ basic PST) behind it
- [ ] Validated in Cute Chess; **beats random mover 100/100**

### Add After Validation — M2 (strong alpha-beta)

- [ ] Negamax alpha-beta + iterative deepening + quiescence
- [ ] Transposition table + hash-move ordering
- [ ] MVV-LVA + killers + history move ordering
- [ ] Real time management (`wtime/btime/winc/binc`) — does not flag
- [ ] Full `info` (`nodes`, `nps`, `seldepth`, `score mate`)
- [ ] (Optional strength) null-move pruning, tapered eval

### Then — M3 (NNUE swap-in + measured Elo)

- [ ] Stockfish labeling pipeline → dataset → game-level train/val split
- [ ] `(768→N)×2→1` NNUE trained in PyTorch/MPS
- [ ] Weight export + engine-side loader; NNUE behind the eval interface
- [ ] `cutechess-cli` gauntlet: NNUE build vs handcrafted build → **measurable Elo gain**
- [ ] (Optional) lichess-bot deployment
- [ ] (Stretch) LMR / aspiration windows / incremental accumulator updates

### Future Consideration (v2+ / later milestones — explicitly deferred)

- [ ] Rust/C++ port of search + eval — when the Python nps ceiling is the binding strength constraint
- [ ] Bucketed / big-net NNUE (HalfKP/HalfKAv2, king buckets, output buckets) — after the plain net proves the pipeline
- [ ] Quantized `.nnue` inference — with the compiled port
- [ ] Syzygy tablebases / opening book, ponder, MultiPV, SMP

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Non-blocking UCI loop + core commands | HIGH | MEDIUM | P1 (M1) |
| Legal movegen + game-end detection | HIGH | LOW | P1 (M1) |
| `evaluate()` swap interface | HIGH | LOW | P1 (M1) |
| Handcrafted material + PST | HIGH | LOW | P1 (M1) |
| GUI validation + beat-random gate | HIGH | LOW | P1 (M1) |
| Alpha-beta + iterative deepening + quiescence | HIGH | MEDIUM | P1 (M2) |
| Transposition table + hash-move ordering | HIGH | MEDIUM | P1 (M2) |
| MVV-LVA / killers / history ordering | HIGH | LOW-MED | P1 (M2) |
| Time management (clock) | HIGH | MEDIUM | P1 (M2) |
| Stockfish labeling → dataset → split | HIGH | MEDIUM | P1 (M3) |
| NNUE model + training loop (MPS) | HIGH | MEDIUM | P1 (M3) |
| NNUE loader wired behind eval interface | HIGH | MEDIUM | P1 (M3) |
| cutechess-cli Elo gauntlet | HIGH | MEDIUM | P1 (M3) |
| Null-move pruning | MEDIUM | MEDIUM | P2 (M2/M3) |
| Tapered eval | MEDIUM | LOW-MED | P2 (M2) |
| LMR / aspiration windows | MEDIUM | MED-HIGH | P2 (M3+) |
| `setoption` (Hash/net/threads) | MEDIUM | LOW-MED | P2 (M2/M3) |
| lichess-bot | MEDIUM | MEDIUM | P2 (M3) |
| Incremental NNUE accumulator | MEDIUM | HIGH | P3 (stretch) |
| Rust/C++ port, big-net NNUE, MCTS, self-play, Syzygy, SMP | (later) | HIGH | P3 (out of scope) |

---

## Competitor / Reference Feature Analysis

| Feature | Stockfish (reference) | Typical Python hobby engine (e.g. Sunfish/others) | Our Approach (ANCE) |
|---------|-----------------------|---------------------------------------------------|---------------------|
| Movegen | Hand-optimized bitboards (C++) | Often `python-chess` or simple boards | `python-chess` legal movegen — correctness over speed |
| Eval | Quantized HalfKAv2 NNUE, incremental | Handcrafted PST, or none | Handcrafted PST → plain `(768→N)×2→1` NNUE (float, full recompute first) |
| Search | Alpha-beta + TT + LMR + null-move + aspiration + SMP | Alpha-beta + a subset | Alpha-beta + TT + quiescence + MVV-LVA/hash ordering (M2); null-move/LMR as differentiators |
| Training | `nnue-pytorch`, binpack data, WDL+eval blend, ~400 epochs, quantized export | Usually none / borrowed nets | Supervised on Stockfish cp labels, game-level split, PyTorch MPS, float export |
| Strength measure | Fishtest SPRT, huge clusters | Ad-hoc | `cutechess-cli` self-play gauntlet, NNUE vs handcrafted, Elo with error bars |
| Protocol | Full UCI incl. MultiPV, ponder, Syzygy, options | Minimal UCI | Minimal-but-correct UCI (M1) → fuller `info` + `setoption` (M2/M3) |

**Read:** We are deliberately trading Stockfish's raw speed/scale for a clean, understandable, swappable-eval Python engine. The bar is not "beat Stockfish" — it is "play legal, tactically sound chess, and get measurably stronger when the NNUE replaces the handcrafted eval."

---

## Sources

- official-stockfish/nnue-pytorch — `docs/nnue.md` and Basic-training-procedure wiki (training pipeline, HalfKP feature set, WDL+eval loss blend, ~400-epoch maturation, lossy quantization export) — MEDIUM (authoritative primary source, cross-checked with training knowledge)
- backscattering.de/chess/uci + Stockfish UCI & Commands docs (minimum command set, `info`/`bestmove`/`score cp`/`score mate`/`pv`/`nps` fields) — MEDIUM→HIGH (canonical, decades-stable spec)
- Chessprogramming Wiki (alpha-beta, iterative deepening, quiescence, MVV-LVA, killers, history, null-move, LMR, TT) — HIGH (established, stable domain knowledge)
- python-chess documentation (legal movegen, FEN parsing, `push`/`pop`, repetition/fifty-move detection, Zobrist hashing) — HIGH
- Project PROJECT.md — committed decisions and out-of-scope boundaries

---
*Feature research for: UCI chess engine (NNUE + alpha-beta, Python/M4)*
*Researched: 2026-07-05*
