# ANCE — A Neural-network Chess Engine

## What This Is

A UCI-compatible chess engine built in Python, whose playing strength comes
from a supervised-trained NNUE-style neural evaluation driving a classical
alpha-beta search. Built for a single Apple Silicon M4 Mac (24 GB unified
memory) as a learning-and-strength project: reach a genuinely strong,
GUI-playable engine without the ruinous compute of AlphaZero-style self-play.

## Core Value

The engine plays legal, tactically sound chess through a clean UCI interface,
and gets measurably stronger when a trained NNUE evaluation replaces the
handcrafted one. If everything else fails, a swappable-eval alpha-beta engine
that loads and runs a trained network must work.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Minimal UCI engine: handles `uci`, `isready`, `ucinewgame`, `position`
      (startpos + fen, with moves), `go`, `stop`, `quit`; always returns a `bestmove`
- [ ] Iterative-deepening alpha-beta search with transposition table,
      quiescence search, and move ordering (MVV-LVA + hash move)
- [ ] Basic time management (`movetime`, `depth`, `wtime/btime/winc/binc`)
- [ ] Swappable evaluation module (handcrafted material + PST placeholder,
      later replaced by NNUE) with a stable interface boundary
- [ ] Supervised NNUE `(768→N)×2→1` trained in PyTorch (MPS) on
      Stockfish-labeled positions
- [ ] NNUE wired in as the leaf evaluation, loadable by the running engine
- [ ] Proper `info depth … score cp … nodes … nps … pv …` output during search
- [ ] Validated in a GUI (Cute Chess / Arena) and playable via lichess-bot
- [ ] Measurable Elo gain (NNUE vs handcrafted eval) confirmed via self-play gauntlet

### Out of Scope

- Rust/C++ hot-path port — deferred to a future milestone; code is structured
  so search + eval can be ported later, but this milestone stays pure Python
- AlphaZero-style self-play RL — infeasible on a single M4; abandoned by the
  canonical hobby project for cost; supervised learning is the chosen shortcut
- AlphaZero/MCTS + deep policy/value net as the engine — NNUE + alpha-beta is
  the committed strength vehicle; MCTS not pursued even as a parallel track
- Cloud/NVIDIA `bullet` training runs — reserved for a later scale-up milestone
- Large bucketed/big-net NNUE architectures — start with the plain 2-perspective
  single-hidden-layer net; scaling deferred

## Context

- **Hardware:** Apple Silicon M4, 24 GB unified memory, macOS. Native arm64
  Python (not Rosetta). The M4 is a capable prototyping/inference machine, not
  a training cluster — its neural throughput for large nets trails NVIDIA GPUs.
- **Training framework:** PyTorch with the MPS backend (primary). MPS is beta —
  no float64, weak FP16/AMP benefit, some unimplemented ops
  (`PYTORCH_ENABLE_MPS_FALLBACK=1`). Recent macOS + PyTorch ≥2.4 recommended.
  MLX is a possible experiment but current evidence favors PyTorch MPS for
  residual/NNUE-style nets on M4-class hardware.
- **Board/UCI plumbing:** `python-chess` provides legal movegen, FEN/PGN, SAN/UCI
  conversion, and repetition/50-move detection. We *are* the engine (write the
  stdin/stdout loop ourselves); `chess.engine` is only for driving external engines.
- **Sparring & labeling:** Local Stockfish (for position labeling and gauntlets)
  and optionally Lc0 (Metal backend) as a superhuman sparring/analysis opponent.
- **Key references:** `official-stockfish/nnue-pytorch` (`docs/nnue.md` is the
  definitive NNUE write-up), `python-chess`, jackdawkins11/pytorch-alpha-zero
  (supervised-first template), foersterrobert/AlphaZeroFromScratch (concepts),
  Dominik Klein's *Neural Networks for Chess*.
- **Reality check:** Pure-Python alpha-beta is orders of magnitude slower than
  C++/Rust. This milestone accepts that ceiling; strength beyond it comes from a
  later compiled port. NNUE roughly halves raw nps but the eval quality more than
  compensates (acts as a search-depth multiplier).

## Constraints

- **Tech stack**: Python 3.12+, `python-chess`, PyTorch (MPS) — matches M4 and
  the Python-first decision
- **Hardware**: Single M4 Mac, 24 GB shared memory — cap batch/minibatch sizes;
  no distributed/multi-GPU training
- **Performance**: Pure-Python search caps strength this milestone; hot-path port
  is explicitly out of scope here
- **Compute budget**: No from-scratch self-play; strength via supervised
  pretraining only. Heavy/large training runs deferred to future cloud/NVIDIA work
- **Architecture boundary**: Evaluation must be a swappable module so the NNUE
  can replace the handcrafted eval without touching the search, and so search+eval
  can later be ported to a compiled language

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| NNUE + alpha-beta as the strength vehicle | Cheapest strength-per-compute on M4; strongest paradigm at equal hardware; mature tooling | — Pending |
| Supervised pretraining, not self-play | AlphaZero self-play infeasible on one M4; supervised is the proven hobby-scale shortcut | — Pending |
| First-net labels from Stockfish evals | Cleanest training signal; standard NNUE approach | — Pending |
| Python-first, defer Rust/C++ port | Fastest path to a working, understandable engine; port when strength pressure is real | — Pending |
| PyTorch MPS over MLX for training | More mature for residual/NNUE nets on M4; evidence favors it | — Pending |
| Plain `(768→N)×2→1` NNUE to start | Beginner-friendly, no buckets; scale later | — Pending |
| Eval as a swappable module | Enables NNUE swap-in and a future compiled port without rewriting search | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-05 after initialization*
