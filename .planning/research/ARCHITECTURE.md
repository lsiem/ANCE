# Architecture Research

**Domain:** UCI chess engine (classical alpha-beta search + NNUE leaf evaluation), pure-Python runtime with a separate PyTorch/MPS offline training pipeline
**Researched:** 2026-07-05
**Confidence:** HIGH (verified against python-chess docs and official-stockfish/nnue-pytorch `docs/nnue.md`; engine layering is well-established prior art)

## Standard Architecture

The system is two programs that share **one artifact and one contract**: the offline trainer *produces* a weights file; the online engine *consumes* it. They never share a process, and — critically — the online engine has **no dependency on PyTorch**. The only thing that crosses the boundary is a versioned weights file whose format is owned by a small shared module.

### System Overview

```
┌───────────────────────────── ONLINE ENGINE (pure Python, no torch) ──────────────────────────────┐
│                                                                                                   │
│   GUI / lichess-bot ──stdin──▶ ┌───────────────┐                                                  │
│                                │  UCI I/O layer │  parse commands, spawn/interrupt search          │
│   GUI / lichess-bot ◀─stdout── │  (main thread)│  emit `info` / `bestmove`                        │
│                                └───────┬────────┘                                                  │
│                                        │ go(position, limits)          stop → Event.set()          │
│                                        ▼                                                           │
│                                ┌───────────────┐   Position (board surface)   ┌────────────────┐  │
│                                │ Search engine │◀────────────────────────────▶│ Board/state    │  │
│                                │ (worker thread)│   push / pop / legal_moves   │ (python-chess) │  │
│                                └───────┬────────┘                             └────────────────┘  │
│                                        │ evaluate(position) -> centipawns (stm-relative)           │
│                                        ▼                                                           │
│                                ┌───────────────────────── Evaluator interface ───────────────────┐│
│                                │   HandcraftedEval (material+PST)   │   NnueEval (loads weights)  ││
│                                └───────────────────────────────────┴─────────────────────────────┘│
└──────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                     │ loads
                              ┌──────────────────────▼───────────────────────┐
                              │   weights file  (net.npz / .safetensors)      │  ◀── THE HANDOFF CONTRACT
                              │   arch id · feature-set id · N · float arrays  │
                              └──────────────────────▲───────────────────────┘
                                                     │ exports
┌──────────────────────────────────── OFFLINE TRAINING (PyTorch + MPS) ─────────────────────────────┐
│  position source ──▶ Stockfish labeler ──▶ dataset shards ──▶ PyTorch model (MPS) ──▶ exporter     │
│  (self-play / PGN /   (cp or WDL score      (.npz / packed    (768→N)×2→1 train      (float arrays │
│   opening FENs)        per FEN)              binary)           loop, val split)       + metadata)  │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility (owns) | Must NOT do | Typical Implementation |
|-----------|-----------------------|-------------|------------------------|
| **UCI I/O layer** | Blocking stdin read loop, tokenize commands, hold current `Position`, launch `go` on a worker, signal `stop`, print `info`/`bestmove`, flush stdout | Contain search or eval logic | `uci/loop.py` main thread + `threading.Thread` worker + `threading.Event` stop flag |
| **Board/state layer** | Legal move generation, make/unmake, FEN/UCI parsing, repetition & 50-move detection, Zobrist key | Make search decisions | Thin `Position` adapter wrapping `chess.Board` (`push`/`pop`/`move_stack`) |
| **Search engine** | Iterative deepening, negamax alpha-beta, TT probe/store, quiescence, move ordering, time management, PV collection, node counting | Read stdin, format UCI strings, know *which* evaluator it holds | `search/` — pure functions over `Position` + `Evaluator` |
| **Evaluator interface** | Single seam: `evaluate(position) -> int` (centipawns, side-to-move relative) | Depend on search internals | `eval/base.py` Protocol/ABC |
| **HandcraftedEval** | Material + piece-square tables baseline | — | `eval/handcrafted.py` |
| **NnueEval** | Load weights file, extract features, run forward pass, return centipawns | Import torch; know about search | `eval/nnue/` (numpy) |
| **NNUE inference** | Feature extraction (768), accumulator, clipped-ReLU, output scale to cp | Training | `eval/nnue/inference.py` + `accumulator.py` |
| **Weight-format module** | Read/write the handoff file; validate arch id, feature-set id, shapes | Anything runtime-specific | `nnue_format/` — imported by BOTH programs |
| **Training pipeline** | Labeling, dataset build, PyTorch model, MPS train loop, export weights | Ship into the engine runtime | `training/` (separate top-level, torch-only) |

## Recommended Project Structure

```
ance/
├── engine/                    # ONLINE runtime — zero torch dependency
│   ├── uci/
│   │   ├── loop.py            # stdin loop, command dispatch, threading
│   │   ├── parser.py          # tokenize `position`/`go`/... into typed commands
│   │   └── protocol.py        # format `info depth … score cp … pv …`, `bestmove`
│   ├── board/
│   │   └── position.py        # Position adapter over chess.Board (the PORT SURFACE)
│   ├── search/
│   │   ├── search.py          # iterative deepening + negamax alpha-beta
│   │   ├── quiescence.py      # capture-only search
│   │   ├── ordering.py        # MVV-LVA + hash move + killers
│   │   ├── tt.py              # transposition table (dict of entries)
│   │   └── timeman.py         # time budget from go limits
│   ├── eval/
│   │   ├── base.py            # Evaluator Protocol  ← THE SWAP SEAM
│   │   ├── handcrafted.py     # material + PST
│   │   └── nnue/
│   │       ├── eval.py        # NnueEval(Evaluator): glue
│   │       ├── features.py    # position → active feature indices (768 set)
│   │       ├── accumulator.py # full recompute now; incremental later
│   │       └── inference.py   # forward pass (numpy)
│   └── main.py                # wire UCI ↔ search ↔ chosen evaluator
├── nnue_format/               # SHARED contract — imported by engine AND training
│   ├── schema.py              # arch id, feature-set id, tensor names, shapes
│   └── io.py                  # save_net(...) / load_net(...) + validation
├── training/                  # OFFLINE — torch/MPS only, never shipped
│   ├── label/                 # Stockfish → (fen, score) via chess.engine
│   ├── data/                  # dataset shards, DataLoader, feature encoding
│   ├── model.py               # (768→N)×2→1 in torch
│   ├── train.py               # MPS train loop, val split, checkpoints
│   └── export.py              # torch state_dict → nnue_format.save_net(...)
└── tools/
    ├── gauntlet.py            # self-play NNUE-vs-handcrafted via chess.engine
    └── parity_check.py        # assert numpy eval == torch eval on FEN set
```

### Structure Rationale

- **`engine/` never imports torch.** The runtime stays lean and fast to start (torch import alone is seconds). NNUE inference is reimplemented in numpy. This is the single most important structural rule.
- **`nnue_format/` is the only shared code.** It is the physical embodiment of the training→engine contract, so both sides break loudly and simultaneously if the format drifts.
- **`board/position.py` is deliberately thin and narrow** — it is the *port surface*. The Rust/C++ port replaces this file plus `search/`; everything the port must reimplement is enumerated in one place (see Port-Readiness pattern).
- **`eval/base.py` sits between search and every evaluator** so NNUE swaps in without search edits.

## Architectural Patterns

### Pattern 1: The Evaluator seam (the swap boundary)

**What:** Search depends only on an abstract `Evaluator`; concrete evals are injected at wiring time.
**When to use:** Always — it is the project's central constraint.
**Trade-offs:** One indirection call per leaf (negligible vs Python search overhead); buys drop-in NNUE swap and A/B gauntlets.

```python
# engine/eval/base.py
from typing import Protocol
from engine.board.position import Position

class Evaluator(Protocol):
    def evaluate(self, pos: Position) -> int:
        """Static eval in centipawns, side-to-move relative (+ = stm better)."""
        ...
```

**Score convention (contract for every evaluator and the whole search):** centipawns, **side-to-move relative** (negamax). Mate as `±(MATE_SCORE - ply)`. Every evaluator returns the same units; swapping eval never changes search sign handling. This convention is what makes the seam real rather than cosmetic.

Selection is a one-liner in `main.py` (env var / UCI `setoption`):
```python
evaluator = NnueEval.load(path) if use_nnue else HandcraftedEval()
searcher = Searcher(evaluator)   # search never learns which one it got
```

### Pattern 2: Narrow port surface (Position adapter)

**What:** Search calls a **small, fixed** set of board operations, all funneled through `Position`. python-chess is an implementation detail hidden behind it.
**When to use:** From day one — retrofitting is expensive.
**Trade-offs:** A wrapper layer over `chess.Board` (thin, cheap); in exchange the future compiled port has a written spec of exactly what a board must provide, and can swap in a bitboard board without touching search.

The entire surface search is allowed to use:
```python
class Position:
    def legal_moves(self) -> list[Move]: ...
    def push(self, m: Move) -> None: ...        # wraps chess.Board.push
    def pop(self) -> Move: ...                   # wraps chess.Board.pop
    def is_check(self) -> bool: ...
    def gives_check(self, m: Move) -> bool: ...
    def is_capture(self, m: Move) -> bool: ...
    def key(self) -> int: ...                    # Zobrist (TT key)
    def is_draw(self) -> bool: ...               # repetition / 50-move / insufficient
    def turn(self) -> bool: ...
```
Anything search wants that is not on this list is a red flag for port-readiness. SAN, PGN, exception-driven control flow — none of it leaks past this wall.

### Pattern 3: Interrupt-by-flag threading (stop-during-go)

**What:** Main thread owns stdin; `go` runs on a worker thread; `stop`/`quit` set a `threading.Event` the search polls at every node (and between iterative-deepening depths). Search returns the best move found so far.
**When to use:** Required by UCI — `stop` must interrupt a running `go`.
**Trade-offs:** The GIL means no true search parallelism, but that is irrelevant here: the pattern is about *responsiveness*, not throughput. The worker owns its **own** `Position` (search copies the board); the shared board is never mutated across threads.

```python
stop = threading.Event()
def handle_go(pos, limits):
    worker = threading.Thread(target=run_search, args=(pos.copy(), limits, stop))
    worker.start()
# on "stop": stop.set()   # search loop checks `if stop.is_set(): break`
```
Polling granularity: check the flag every N nodes (e.g. 2048) to avoid `Event.is_set()` overhead in the hot path.

### Pattern 4: NNUE — full recompute first, incremental accumulator later

**What:** The NNUE seam starts **stateless** (`evaluate(pos)` recomputes the accumulator from the ~30 active features every call). Incremental update is a later optimization layered on the *same* seam.
**When to use:** Full recompute for correctness/first-strength; incremental only once nps matters.
**Trade-offs:** Full recompute is O(active_features × N) per leaf — fine in Python where search overhead dominates. Incremental (copy previous accumulator, subtract removed feature columns, add new ones — per `nnue.md`, ~2 column ops for a quiet move vs reprocessing all pieces) is faster but couples the accumulator to make/unmake.

Verified design from `official-stockfish/nnue-pytorch/docs/nnue.md`:
- **Feature set:** simple "all-piece-squares" = **768 inputs** (64 squares × 6 piece types × 2 colors), ~30 active per position. (HalfKP's 40,960 = 64 king squares × 640 is explicitly out of scope for M1.)
- **Two perspectives:** one accumulator from the side-to-move's view, one from the opponent's; concatenated `[stm_acc, opp_acc]` → the `×2` in `(768→N)×2→1`. This lets the net learn tempo.
- **Forward pass (float, pure Python/numpy):** `acc = bias + Σ W[:, f] for active f`; `h = clippedReLU(acc)`; `out = h·W_out + b_out`; scale to centipawns.

The incremental version, when built, hooks the Position's push/pop:
```python
# later optimization — maintained as a stack alongside the search
def on_push(self, move):   # add new feature cols, subtract removed ones
    ...
def on_pop(self):          # restore previous accumulator (or pop a saved copy)
    ...
```
`python-chess` `push`/`pop` + `move_stack` give exactly the make/unmake hooks this needs — verified in the docs.

### Pattern 5: Transposition table entries carry bound + depth

**What:** TT stores `(key, depth, score, bound, best_move)` where `bound ∈ {EXACT, LOWER, UPPER}`.
**When to use:** Always — a TT that stores only scores is unsound with alpha-beta.
**Trade-offs:** Python `dict` keyed by Zobrist is simple and correct; a fixed-size array with replacement is the port target. Use `chess.polyglot.zobrist_hash` (or an incrementally-maintained key) for `Position.key()` — recomputing the full hash every node is a known python-chess hot-spot to watch.

## Data Flow

### Online: one `go` command

```
GUI: "position startpos moves e2e4 …"      GUI: "go wtime … btime …"
        │                                           │
        ▼                                           ▼
  UCI parser sets Position              UCI spawns worker(pos.copy(), limits)
                                                    │
                        ┌───────────────────────────┘
                        ▼
      Searcher: for depth in 1..∞ (iterative deepening):
          negamax(pos, depth, α, β):
              if leaf/quiet → Evaluator.evaluate(pos)  ──▶ centipawns (stm-relative)
              order moves (hash move, MVV-LVA), push/pop, recurse
              probe/store TT ; poll stop Event ; check time
          emit "info depth D score cp S nodes N nps … pv …"
        │
        ▼
  time up / stop / max depth  →  emit "bestmove <uci>"
```

### Offline: positions → weights

```
position source (opening FENs / PGN games / light self-play)
        │  fen strings
        ▼
Stockfish labeler  (drive via python-chess chess.engine, fixed depth/nodes)
        │  (fen, score_cp)  or  (fen, wdl)      ← the training signal
        ▼
dataset shards  (.npz / packed binary: encoded 768-feature indices + label)
        │
        ▼
PyTorch model (768→N)×2→1 on MPS  — train loop, val split, checkpoint
        │  torch state_dict
        ▼
export.py  →  nnue_format.save_net(arrays, meta)  →  net.npz
        │
        ▼
        (parity_check.py: numpy forward == torch forward on held-out FENs)
        │
        ▼
engine NnueEval.load("net.npz")  →  swapped in behind the Evaluator seam
```

### The training→engine handoff contract

The **only** artifact crossing the boundary. Recommended: a single `.npz` (or `.safetensors`) file — plain float32 arrays plus a metadata header — deliberately **not** a torch `.pt`, so the engine needs zero torch.

`nnue_format/schema.py` fixes the contract:

| Field | Type | Purpose |
|-------|------|---------|
| `format_version` | int | Bump on any breaking change |
| `arch_id` | str | e.g. `"768x2-N-1"` |
| `feature_set` | str | `"board768"` — engine feature extractor must match |
| `hidden_size` (N) | int | Validates array shapes |
| `perspective` | bool | Two-perspective concat expected |
| `ft.weight` | float32 `[768, N]` | Feature transformer |
| `ft.bias` | float32 `[N]` | Accumulator bias |
| `out.weight` | float32 `[2N, 1]` | Output layer |
| `out.bias` | float32 `[1]` | Output bias |
| `output_scale` | float | cp = raw × scale |
| *(later)* `quant.*` | — | int8/int16 scales if a quantized net is exported |

`load_net` **validates arch_id, feature_set, and every shape and fails loudly** on mismatch — a wrong-shaped or wrong-feature-set net must never silently load. This is the enforcement point that keeps the two programs honest.

## Build Order (dependency-honoring)

Each step is independently testable in a GUI or by unit test before the next begins.

1. **UCI skeleton.** stdin loop + parser + threading + `bestmove` returning a random/first legal move. `uci`/`isready`/`ucinewgame`/`position`/`go`/`stop`/`quit`. **Validate in Cute Chess immediately** — proves the plumbing before any chess strength exists.
2. **Board adapter.** `Position` over `chess.Board` exposing the narrow port surface; wire `position` command into it.
3. **Search core.** Iterative deepening + negamax alpha-beta + `info`/PV output + time manager, using a *trivial inline material eval*. Now it plays real (weak) chess and reports depth/score/nps.
4. **Formalize the Evaluator seam + strengthen search.** Extract `Evaluator` Protocol; implement `HandcraftedEval` (material+PST) as the first real eval behind the seam. Add TT (bound+depth), quiescence, MVV-LVA + hash-move ordering. **This is the milestone-critical fallback engine** — a swappable-eval alpha-beta engine that already works.
5. **Offline training pipeline** *(can start in parallel after step 1 — it shares only `nnue_format/`)*. Stockfish labeling → dataset → `(768→N)×2→1` PyTorch/MPS train loop → `export.py`. Independent of the running engine except the contract.
6. **NNUE inference + swap-in.** `NnueEval` (numpy, **full recompute**) implementing `Evaluator`; load the exported net; run `parity_check.py` (numpy == torch on FENs). Swap NNUE in behind the seam via `setoption`/env — **search code unchanged**. Run a self-play gauntlet NNUE-vs-handcrafted to confirm the Elo gain.
7. **(Optional this milestone) Incremental accumulator.** Wire accumulator update/restore to `Position.push`/`pop`. Pure optimization on the existing seam.

**Ordering rationale:** UCI first de-risks the interface (fast GUI feedback). Search+handcrafted eval gives the guaranteed-working fallback the Core Value demands *before* any ML risk. Training is decoupled (only the contract binds it) so it can proceed alongside. NNUE arrives last as a *swap*, not a rewrite — which is the whole point of the seam.

## Anti-Patterns

### Anti-Pattern 1: Shipping torch into the engine runtime
**What people do:** `import torch` in the eval to reuse the training model.
**Why it's wrong:** Multi-second startup, heavy dependency, couples runtime to training, and blocks the future compiled port.
**Do this instead:** Reimplement the forward pass in numpy; cross the boundary only via the `nnue_format` file. Verify equivalence with `parity_check.py`.

### Anti-Pattern 2: Leaking python-chess conveniences into search
**What people do:** Use SAN, PGN objects, or python-chess exceptions inside the search hot path.
**Why it's wrong:** Slow, and unportable — the compiled board won't have these, so the port becomes a rewrite.
**Do this instead:** Confine search to the narrow `Position` surface (Pattern 2). If search needs something new, add it to that surface deliberately.

### Anti-Pattern 3: Eval swap that isn't really a swap
**What people do:** Different evaluators return different units/sign conventions, so search has `if nnue: … else: …`.
**Why it's wrong:** The seam is fake; you cannot A/B, and NNUE integration touches search.
**Do this instead:** Enforce one contract — centipawns, side-to-move relative, mate as `±(MATE-ply)` — for every evaluator.

### Anti-Pattern 4: Sharing a mutable board across threads
**What people do:** Worker searches the same `chess.Board` the UCI thread holds.
**Why it's wrong:** `chess.Board` is not thread-safe; `stop`/`position` races corrupt state.
**Do this instead:** Search gets `pos.copy()`; communication is only via the `threading.Event` stop flag and the returned bestmove.

### Anti-Pattern 5: TT storing bare scores; recomputing Zobrist per node
**What people do:** Cache only score, or call `zobrist_hash` from scratch at every node.
**Why it's wrong:** Bare scores make alpha-beta unsound (bounds differ from exact values); full-hash recompute is a python-chess hotspot.
**Do this instead:** Store `(depth, score, bound, best_move)`; maintain the key incrementally or measure the hash cost early.

### Anti-Pattern 6: Coupling incremental NNUE to search before it's correct
**What people do:** Build the incremental accumulator before the full-recompute eval is verified.
**Why it's wrong:** Two moving parts (net correctness + update correctness) fail together, hard to bisect.
**Do this instead:** Full recompute → parity-check → *then* add incremental as an optimization behind the same seam (Pattern 4).

## Integration Points

### External Services / Tools

| Tool | Integration Pattern | Notes |
|------|---------------------|-------|
| Stockfish | Offline: drive via `python-chess` `chess.engine` (UCI) for labeling + gauntlet | Fixed depth or node count for consistent labels; runs in `training/`+`tools/`, never in engine runtime |
| Cute Chess / Arena | GUI runs *our* engine as a UCI child process | Primary manual validation from step 1; also runs tournaments |
| lichess-bot | Wraps the engine binary/script as a UCI engine | No engine code change — it just speaks UCI |
| Lc0 (optional) | Superhuman sparring/analysis opponent via UCI | Metal backend on M4; analysis only |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| UCI ↔ Search | function call `go(pos, limits)` + `threading.Event` stop | No shared mutable board; worker owns a copy |
| Search ↔ Board | narrow `Position` surface (push/pop/legal_moves/key/…) | The port surface — keep it small and written down |
| Search ↔ Eval | `Evaluator.evaluate(pos) -> int` | The swap seam; one unit/sign contract |
| Engine ↔ Training | `nnue_format` weights file only | No code sharing beyond `nnue_format/`; engine has no torch |
| Training internal | Stockfish → dataset → model → exporter | Each stage writes an artifact the next reads (resumable) |

## Scaling Considerations

"Scale" here is **playing strength / nodes-per-second**, not users.

| Stage | Architecture adjustments |
|-------|--------------------------|
| First working engine | Correctness over speed: full-recompute NNUE, dict TT, python-chess board. Accept low nps. |
| Squeeze pure-Python | Incremental accumulator; incremental Zobrist; fixed-size TT; profile move ordering; reduce per-node object churn. |
| Break the Python ceiling (out of scope this milestone) | Port `search/` + `board/position.py` to Rust/C++ against the *same* Evaluator/Position contracts and the *same* weights file. The narrow surfaces are what make this a port, not a rewrite. |

### Scaling Priorities

1. **First bottleneck: pure-Python search overhead** (movegen, per-node objects). Fix order: incremental accumulator, incremental hash, fixed-size TT — *before* considering a port.
2. **Second bottleneck: eval quality vs nps trade** — NNUE ~halves nps but multiplies effective depth via better eval (per PROJECT.md reality check). Measure net strength by gauntlet Elo, not nps alone.

## Sources

- official-stockfish/nnue-pytorch — `docs/nnue.md` (accumulator, two-perspective concat, 768 vs HalfKP 40960 feature sets, quantization: int16 accumulator / int8 hidden ×64 / clipped-ReLU [0,127] / int32 biases / output scale) — HIGH, primary
- niklasf/python-chess docs — `Board.push`/`pop`/`move_stack`, `can_claim_*` / `halfmove_clock` repetition & 50-move detection, `chess.engine` for driving Stockfish — HIGH, primary (v1.11.2)
- jackdawkins11/pytorch-alpha-zero, foersterrobert/AlphaZeroFromScratch — structural reference for offline-training vs online-engine separation — MEDIUM, adapted (not AlphaZero here)
- Established alpha-beta engine architecture (iterative deepening, TT bound flags, quiescence, MVV-LVA) — HIGH, well-documented prior art

---
*Architecture research for: UCI chess engine (alpha-beta + NNUE), Python runtime + PyTorch/MPS offline training*
*Researched: 2026-07-05*
