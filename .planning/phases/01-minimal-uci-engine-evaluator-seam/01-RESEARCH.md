# Phase 1: Minimal UCI Engine & Evaluator Seam - Research

**Researched:** 2026-07-05
**Domain:** Hand-written UCI protocol I/O loop, non-blocking threading, minimal fixed-depth negamax substrate, handcrafted material+PST evaluation, python-chess board plumbing — pure Python, zero external services
**Confidence:** HIGH on UCI protocol contract, python-chess exception semantics, and the Simplified Evaluation Function tables (all directly fetched from primary sources); MEDIUM on exact non-blocking threading idiom (well-established community pattern, not a single canonical spec); LOW-risk gaps flagged in Open Questions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-00a:** The eval seam is `evaluate(position) -> centipawns`, **side-to-move
  relative**, mate scored as ±(MATE − ply). NNUE must drop in later with **zero
  search-side change**. *(EVAL-01, roadmap decision)*
- **D-00b:** A **non-blocking reader/worker threading model** — the stdin reader
  never blocks, so `stop`/`quit` are honored even mid-search. *(roadmap decision,
  UCI-12)*
- **D-00c:** Board state, legal movegen, FEN/SAN/UCI conversion, and
  repetition/50-move detection all come from **`python-chess` (`chess`)**; we
  hand-write the UCI I/O loop ourselves — `chess.engine` is NOT used to speak the
  protocol. *(PROJECT.md, CLAUDE.md)*
- **D-01:** Phase 1 uses a **minimal fixed-depth negamax** — NO alpha-beta
  pruning, NO quiescence, NO iterative deepening. It honors `go depth <n>` and
  `go movetime <ms>` for real and evaluates every leaf through the seam.
- **D-02:** A bare `go` (no depth/movetime/clock) searches to a **fixed default
  depth** (choose a value that completes in well under a second in pure Python,
  ~3–4 to start; the planner may tune). Fully deterministic and always terminates.
- **D-03:** `go movetime <ms>` and `stop` **abort and return the best root move
  found so far** (root-level best tracking, since there is no ID yet).
- **D-04:** On tied eval scores, pick **uniformly at random among all equal-best
  moves**, using a **seedable RNG** (fixed seed in tests for reproducibility).
- **D-05:** Base on the **Simplified Evaluation Function** (Tomasz Michniewski):
  piece values P=100, N=320, B=330, R=500, Q=900; one single-phase PST per piece;
  plus its two king tables (middlegame vs endgame) selected by a discrete
  material-count phase check (**not** tapering).
- **D-06:** Add these cheap, symmetric positional terms on top of material+PST:
  **mobility** (side-to-move legal-move-count difference), **bishop pair**
  bonus, **tempo** bonus (side to move), and **pawn-structure penalties**
  (doubled + isolated pawns).
- **D-07:** All eval terms are **symmetric and side-to-move relative** per the
  D-00a seam contract.
- **D-08:** `id name ANCE 0.1`, `id author Lasse Siemoneit`.
- **D-09:** Declare **zero `option` lines** in M1 (emit only id + `uciok`).
  Accept any `setoption` command **silently without crashing**.
- **D-10:** `position fen <malformed>` or an illegal move in a `moves` list →
  **reject the command and keep the current board untouched**, emitting an
  `info string` noting the error. Never crash.
- **D-11:** Unknown/unsupported commands → **silently ignored** per the UCI
  spec (skip the unknown leading token, attempt to parse the rest of the line).
- **D-12:** `go` in a **zero-legal-move position** (checkmate/stalemate) →
  emit **`bestmove (none)`** (Stockfish convention). Must return promptly.
- **D-13:** A single search worker thread; the reader sets a shared
  **`threading.Event` cancel flag** (plus a deadline) on `stop`/`quit`/timeout.
  The worker checks the flag **every ~1024–2048 nodes and at each root move**,
  aborting to return best-so-far. `quit` sets the flag, lets the worker unwind,
  then exits cleanly.
- **D-14:** stdout is flushed on **every line**.
- **D-15:** Ship an **`ance/` package with `__main__.py`**, launched via
  `python -m ance`. Modular layout (uci / search / eval separated).
- **D-16:** `go infinite` searches to the default depth, then **idles holding
  the result until `stop` arrives**, only then emitting `bestmove`.
- **D-17:** `ucinewgame` is a **no-op reset of per-game state** in M1 (may
  reset the board and reseed the tie-break RNG).
- **D-18:** A **stderr-only** diagnostic channel, off by default, toggled by
  UCI `debug on/off` (and optionally `ANCE_DEBUG` env var).

### Claude's Discretion

- Exact default search depth value (D-02) — planner tunes to pure-Python speed.
- Internal module/file names and the precise node-count polling interval (D-13).
- Whether the debug channel (D-18) also honors an `ANCE_DEBUG` env var in
  addition to UCI `debug on/off`.
- Precise `info string` wording for rejected input.

### Deferred Ideas (OUT OF SCOPE)

- `setoption` / configurable Hash/net-path/threads — v2 (CFG-01).
- Tapered (midgame/endgame) evaluation — v2 (EVAL-04).
- Console-script (`ance`) entry point via pyproject — deferred; `python -m ance`
  for M1.
- Caching/incremental mobility — optimize when real search arrives (Phase 2+).
- Fail-soft alpha-beta, iterative deepening, quiescence — Phase 2.
- `info depth … pv …` search output — Phase 2 (UCI-11).
- Transposition table, move ordering, `wtime/btime` clock control — Phase 3.
- NNUE eval and training — Phases 4–5.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UCI-01 | `uci` → `id name`/`id author`/`uciok` | UCI Protocol Contract section; exact wording verified from primary spec |
| UCI-02 | `isready` → `readyok`, never blocks | UCI Protocol Contract + Threading Model section (readyok answered from reader thread, never gated behind search) |
| UCI-03 | `ucinewgame` resets per-game state (no-op M1) | D-17; Architecture — `ucinewgame` handler resets `Position` + RNG seed |
| UCI-04 | `position startpos [moves ...]` | python-chess API section — fresh `Board()` + `push_uci` per move, never diff old board |
| UCI-05 | `position fen <fen> [moves ...]`, rejects malformed FEN without crash | python-chess API section — `ValueError`/`IllegalMoveError`/`InvalidMoveError` catch strategy |
| UCI-06 | Every `go` yields exactly one legal `bestmove`, never hangs | Threading Model + Negamax Substrate + `bestmove (none)` convention |
| UCI-07 | `go movetime <ms>` and `go depth <n>` honored | Negamax Substrate section — root-level best tracking, deadline check |
| UCI-09 | `stop` ends search promptly, emits current `bestmove` | Threading Model — `Event` polling granularity |
| UCI-10 | `quit` clean exit, never deadlocks on running search | Threading Model — flag-set + bounded `join()` |
| UCI-12 | stdin/stdout loop stays readable during search (non-blocking) | Threading Model section |
| SRCH-01 | Only legal moves generated; checkmate/stalemate/draws via python-chess | python-chess API section |
| EVAL-01 | Stable `evaluate(position) -> cp` interface, stm-relative, mate ±(MATE−ply) | Evaluator Seam Design section |
| EVAL-02 | Handcrafted material+PST evaluator (M3 baseline) | Handcrafted Evaluation section — full Simplified Eval tables |
| TOOL-01 | Loads and plays a full legal game in a GUI | Environment Availability (Cute Chess/Arena/Stockfish audit) + Validation Architecture |
| TOOL-02 | Beats a random-mover opponent 100/100 | Testing & Tooling section — self-play harness pattern |
</phase_requirements>

## Summary

Phase 1 is a pure-Python, zero-network-dependency engineering problem: hand-write
a UCI stdin/stdout loop that never blocks, wire it to `python-chess` for all
board legality, and drive a intentionally-dumb fixed-depth negamax through a
swappable `evaluate(position) -> cp` seam. Every piece of this phase has an
authoritative, verifiable source: the UCI command/response contract is a
20-year-old stable text protocol (verified against the canonical DOBRO gist and
chessprogramming.org), `python-chess` 1.11.2's exception hierarchy for malformed
FEN/illegal moves is documented and confirmed (`InvalidMoveError`,
`IllegalMoveError` — both `ValueError` subclasses, so a single `except ValueError`
at the `position`-command boundary satisfies D-10), and the handcrafted eval is
a byte-for-byte reproduction of the well-known Michniewski Simplified Evaluation
Function (verified from chessprogramming.org, exact piece values and all six
piece-square tables below). The one genuinely under-specified area is the
non-blocking threading idiom itself — there is no single "UCI threading spec,"
only community convention — but the shape is simple and low-risk: a blocking
`readline()` on the main thread (this is fine — it's the *only* thing that
thread does), a daemon worker thread per `go`, and a `threading.Event` the
worker polls every ~1024–2048 nodes.

**Primary recommendation:** Build the walking skeleton in this order — (1) `ance/`
package + `__main__.py` speaking bare `uci`/`isready`/`quit` and returning a
first-legal-move `bestmove` (proves the process boundary and GUI/pipe handshake
before any chess logic exists), (2) wire `python-chess` behind a narrow
`Position` adapter for `position`/`ucinewgame`, (3) add the threaded
reader/worker + `Event` stop mechanism and prove `stop`/`quit` never hang via a
piped test, (4) add the fixed-depth negamax against a trivial material-only
eval so `go depth`/`go movetime` are real, (5) formalize the `Evaluator`
Protocol and swap in the full Simplified-Eval handcrafted evaluator, (6) harden
malformed-FEN/illegal-move/zero-legal-move handling, (7) build the random-mover
self-play harness and drive it to 100/100, (8) manually validate in Cute Chess
or Arena. Each step is independently testable before the next begins — do not
build the full eval before the threaded loop is proven non-blocking.

## Architectural Responsibility Map

This project is a local CLI/protocol engine, not a networked application, so
the standard Browser/API/DB tiers do not apply. The equivalent tier boundaries
for a UCI engine (already fixed by the project's own `ARCHITECTURE.md`) are:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Protocol parsing (`uci`/`position`/`go`/...) & response formatting | UCI I/O layer (main thread) | — | Owns stdin/stdout; must never contain chess logic or block |
| Board legality, FEN/UCI parsing, terminal detection | Board adapter (`Position`) over `chess.Board` | — | The narrow port surface; python-chess is an implementation detail behind it (per project ARCHITECTURE.md Pattern 2) |
| Move selection (fixed-depth negamax) | Search substrate (worker thread) | — | Pure function of `Position` + `Evaluator`; owns node counting, stop-flag polling, root move tracking |
| Static position scoring | Evaluator (`HandcraftedEval`) | — | Implements the `Evaluator` Protocol; the swap seam for Phase 5's NNUE |
| Threading/cancellation | UCI I/O layer (spawns) + Search substrate (polls) | — | Reader thread never blocks; worker thread is the only place `stop_flag.is_set()` is checked |
| Test/tooling (self-play harness, GUI validation) | External to runtime (`tools/`, `tests/`) | — | Drives the engine as a subprocess/UCI child; never imports engine internals directly except via the `Evaluator`/`Position` seams for unit tests |

**Cross-check against ARCHITECTURE.md:** This map is a strict subset of the
project-level Component Responsibilities table already in
`.planning/research/ARCHITECTURE.md` — Phase 1 builds the UCI I/O layer, Board
adapter, a *minimal* Search engine (no TT/ordering/quiescence yet), and
`HandcraftedEval` only. No misassignment risk identified: this phase does not
touch NNUE, TT, or time-management tiers.

## Standard Stack

No new packages beyond what `.planning/research/STACK.md` already approved at
project level. Phase 1 uses only:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ (native arm64) | Runtime | Project-locked (CLAUDE.md); see Environment Availability for what's actually installed on this machine |
| `chess` (python-chess) | 1.11.2 | Board state, legal movegen, FEN/UCI parsing, terminal/draw detection | `[VERIFIED: pypi registry]` — `pip3 index versions chess` confirms `1.11.2` is the current release, matching the version pinned in CLAUDE.md and STACK.md |
| `pytest` | 8.4.2 | UCI-loop, board-adapter, and eval-seam tests | `[VERIFIED: pypi registry]` — `pip3 index versions pytest` confirms `8.4.2` current |

### Supporting
None new for this phase. `threading` and `random` are stdlib — no install needed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written UCI loop | `chess.uci` / `chess.engine` module | Explicitly rejected project-wide — that module is a UCI *client* (drives external engines), not a server; ANCE must speak UCI on its own stdin/stdout (D-00c) |
| `threading.Event` + polling | `asyncio` | python-chess's `Board` and the intended future compiled port favor a simple synchronous worker-thread model; asyncio adds complexity with no benefit here since there is exactly one long-running task (search) to cancel |

**Installation:**
```bash
python3.13 -m venv .venv && source .venv/bin/activate   # see Environment Availability — 3.12 itself not installed on this machine, 3.13 satisfies "3.12+"
pip install chess pytest
```

**Version verification performed:**
```bash
pip3 index versions chess    # -> chess (1.11.2) [current]
pip3 index versions pytest   # -> pytest (8.4.2) [current]
```
Both confirmed current via the PyPI registry directly (not training-data recall).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `chess` | PyPI | Published to this name since 2025-02 under a project with 10+ years of prior history as `python-chess` | Unknown (registry query returned no download stat) | `github.com/niklasf/python-chess` (confirmed, active, high reputation) | `[SUS]` (reason: `unknown-downloads` — a data-availability gap in the legitimacy tool, not a signal of a suspicious package) | **Approved.** Already the project's pinned dependency (CLAUDE.md, STACK.md), verified current on PyPI, backed by a well-known GitHub repo with Context7-indexed official docs. Planner should still add a lightweight `checkpoint:human-verify` before the `pip install` step per protocol, but this is a formality — treat as effectively `[VERIFIED]`. |
| `pytest` | PyPI | 18+ years old project; flagged `too-new` only because the *latest patch* (8.4.2) was published recently | Unknown (same tool gap) | `github.com/pytest-dev/pytest` (confirmed, one of the most widely used Python test frameworks) | `[SUS]` (reasons: `too-new`, `unknown-downloads` — both false-positive signals for a mature, ubiquitous package) | **Approved.** Same reasoning as above; planner should still gate the install behind a `checkpoint:human-verify` per protocol, but no real risk identified. |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `chess`, `pytest` — both false positives caused by the legitimacy tool lacking PyPI download-count data and misreading "latest release date" as package age; both are long-established, high-reputation packages already vetted at project level in `.planning/research/STACK.md`. Planner should add a single lightweight `checkpoint:human-verify` before the first `pip install` step (covers both packages at once) rather than treating this as a real risk signal.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────┐
                         │   GUI / pipe script / pytest harness     │
                         └───────────────┬───────────┬─────────────┘
                                stdin     │           │ stdout
                                          ▼           │
                         ┌────────────────────────────┴────────────┐
                         │   UCI I/O loop (main thread)             │
                         │   readline() → tokenize → dispatch       │
                         │   writes id/uciok/readyok/bestmove/info  │
                         │   (flush=True on every line — D-14)      │
                         └───────┬───────────────────────┬──────────┘
             "position ..."     │                        │ "go ..."
                                 ▼                        ▼
                    ┌────────────────────┐   spawn   ┌─────────────────────────┐
                    │ Position adapter   │◀──────────│ Search worker (thread)  │
                    │ (wraps chess.Board)│  pos.copy()│ fixed-depth negamax     │
                    │ fresh Board() per  │           │ polls stop_flag every   │
                    │ `position` cmd,    │           │ ~1024-2048 nodes +      │
                    │ push_uci per move  │           │ at each root move       │
                    └────────────────────┘           └───────────┬─────────────┘
                                                                  │ evaluate(pos)->cp
                                                                  ▼
                                                    ┌───────────────────────────┐
                                                    │ Evaluator seam (Protocol) │
                                                    │  HandcraftedEval          │
                                                    │  (material+PST+mobility+  │
                                                    │   bishop-pair+tempo+      │
                                                    │   pawn-structure)         │
                                                    └───────────────────────────┘
        "stop"/"quit" ──▶ threading.Event.set() ──▶ worker checks flag, returns
                                                     best-root-move-so-far ──▶
                                                     UCI loop emits "bestmove ..."
```

A reader can trace: GUI sends `position` + `go` → main thread parses and hands
a **copy** of the board to a new worker thread → worker calls
`Evaluator.evaluate()` at every leaf, tracking the best root move → `stop` (or
a deadline, or depth exhaustion) sets the `Event` → worker returns → main thread
emits exactly one `bestmove` line, flushed immediately.

### Recommended Project Structure

Adopt the `engine/` layout from `.planning/research/ARCHITECTURE.md`, scoped to
what Phase 1 actually builds (omit `nnue/`, `training/`, `tt.py`,
`ordering.py`, `timeman.py` — those are Phase 2/3/4/5):

```
ance/
├── __main__.py             # `python -m ance` entry point (D-15)
├── uci/
│   ├── loop.py             # readline loop, dispatch, threading, flush (D-14)
│   ├── parser.py           # tokenize position/go/... into typed commands
│   └── protocol.py         # format id/uciok/readyok/bestmove/info lines
├── board/
│   └── position.py         # Position adapter over chess.Board (D-00c, D-10)
├── search/
│   └── negamax.py          # fixed-depth negamax, root move tracking (D-01..D-04)
├── eval/
│   ├── base.py             # Evaluator Protocol (D-00a) — THE SWAP SEAM
│   └── handcrafted.py      # Simplified Eval + D-06 terms (D-05..D-07)
└── tools/
    └── random_mover_gauntlet.py   # TOOL-02 self-play harness
tests/
├── conftest.py              # subprocess-driving fixture
├── test_uci_handshake.py
├── test_position_command.py
├── test_go_bestmove.py
├── test_eval_seam.py
└── test_random_mover_gauntlet.py
```

### Pattern 1: UCI Protocol Contract (verified wording)

**What:** The exact command/response semantics, fetched from the canonical UCI
description (DOBRO gist, cross-checked against chessprogramming.org/UCI and
Stockfish's own docs).
**When to use:** Every command handler in `uci/parser.py` / `uci/protocol.py`.

`[CITED: gist.github.com/DOBRO/2592c6dad754ba67e6dcaec8c90165bf, chessprogramming.org/UCI]`

| GUI → Engine | Exact semantics |
|---|---|
| `uci` | "tell engine to use uci, sent once as the first command after program boot" → engine replies with `id name <x>`, `id author <y>`, then (zero option lines per D-09), then `uciok` |
| `isready` | "used to synchronize the engine with the GUI... must always be answered with `readyok`" — including mid-initialization, mid-search |
| `ucinewgame` | "sent when the next search will be from a different game" — no required response |
| `position [fen <fenstring> \| startpos] moves <m1> ... <mi>` | "set up the position ... and play the moves on the internal board" |
| `go` | "start calculating on the current position"; sub-params: `depth x` = "search x plies only"; `movetime x` = "search exactly x msec"; `infinite` = "search until `stop`. Do not exit... without being told"; `nodes x`; `wtime`/`btime`/`winc`/`binc` (parse for Phase 1, honor only movetime/depth for real per D-01, ignore clock params without crashing — full clock handling is Phase 3/UCI-08) |
| `stop` | "stop calculating as soon as possible, don't forget the `bestmove`" |
| `quit` | "quit the program as soon as possible" |
| `debug [on\|off]` | "switch the debug mode of the engine on and off" (D-18: stderr-only channel) |

| Engine → GUI | Exact semantics |
|---|---|
| `id name <x>` / `id author <y>` | sent once, immediately after receiving `uci` |
| `uciok` | "sent after id and optional options to tell the GUI the engine ... is ready in uci mode" |
| `readyok` | "sent when the engine has received `isready` and has processed all input" — must never be gated behind a running search |
| `bestmove <move> [ponder <move2>]` | "must always be sent if the engine stops searching" — required after **every** `go`, with no exception for terminal positions |
| `info string <str>` | "the rest of the line is interpreted as `<str>`" — free text, safe channel for D-10's rejected-input notices |

**`bestmove (none)` convention (D-12):** `[CITED: talkchess.com UCI nullmove thread, chessprogramming.org]` The spec is silent on the exact token for "no legal move," but the community/Stockfish convention is `bestmove (none)` (a token the GUI is required to ignore as unrecognized, satisfying the "always send bestmove" rule without claiming a fake move exists); `bestmove 0000` (the UCI null-move notation) is the more strictly spec-compliant alternative. D-12 already locks `(none)` for SF gauntlet-log parity — implement exactly that string.

### Pattern 2: python-chess exception contract (verified from Context7 + GitHub)

`[CITED: Context7 /niklasf/python-chess v1.11.2; github.com/niklasf/python-chess/issues/800, /369]`

```python
import chess

# --- position fen <malformed> --- (UCI-05, D-10)
try:
    board = chess.Board(fen_string)   # or board.set_fen(fen_string)
except ValueError as e:
    # malformed FEN: syntactically bad, wrong row count, bad castling rights, etc.
    # ALL raise plain ValueError (or a ValueError subclass) — one except clause covers it
    emit_info_string(f"invalid fen: {e}")
    return  # keep the previous board untouched — D-10

# --- position ... moves <illegal-or-malformed-move> --- (D-10)
try:
    board.push_uci(move_str)
except chess.InvalidMoveError:    # syntactically bad UCI, e.g. "z9z9"
    emit_info_string(f"invalid move syntax: {move_str}")
    return
except chess.IllegalMoveError:    # syntactically valid but illegal here
    emit_info_string(f"illegal move: {move_str}")
    return
# Both InvalidMoveError and IllegalMoveError subclass ValueError,
# so `except ValueError:` alone is a valid single-catch strategy for D-10
# if per-case wording isn't needed.
```

Key facts verified this session (not from training-data recall alone):
- `Board.push_uci()` = `push(parse_uci(uci))`; `parse_uci` validates the move
  is legal **in the current position** — it is not a pure syntax parser.
- `chess.InvalidMoveError` (bad syntax) and `chess.IllegalMoveError` (illegal in
  position) both exist as of the current release and both subclass `ValueError`
  — confirmed via the CHANGELOG and GitHub issue threads.
- `Move.from_uci()` raises `ValueError` on malformed UCI strings (changed from
  `IndexError` in older releases — 1.11.2 is well past that change).
- `set_fen()` / `Board(fen=...)` raise `ValueError` on malformed FEN (bad row
  count, non-position-part content, etc.).
- `is_checkmate()`, `is_stalemate()`, `is_insufficient_material()`,
  `is_game_over()` — direct terminal-detection calls (SRCH-01).
- `is_fivefold_repetition()` / `is_seventyfive_moves()` are automatic-draw
  checks (no claim needed); `can_claim_threefold_repetition()` /
  `can_claim_fifty_moves()` are the claimable (non-automatic) variants —
  Phase 1 doesn't need draw claiming logic (that's a search-tree concern for
  Phase 2's SRCH-07), but `is_game_over()` alone is sufficient for D-12's
  zero-legal-move / terminal check in this phase.
- `board.copy()` — use this to hand the worker thread its own board instance;
  `chess.Board` is not documented as thread-safe (confirmed via project-level
  `ARCHITECTURE.md` Anti-Pattern 4 — do not share a mutable `Board` across
  threads).

### Pattern 3: Non-blocking reader/worker threading model

`[ASSUMED — cross-checked against the project's own PITFALLS.md Pitfall 1/2, which is itself HIGH-confidence prior research]`

There is no single canonical "UCI threading spec" — this is community
convention, not a documented API. The shape that satisfies D-00b/D-13/UCI-12:

```python
import threading, sys

stop_flag = threading.Event()
worker: threading.Thread | None = None

def main_loop():
    for line in sys.stdin:                 # blocking readline is fine here —
        handle_command(line.strip())       # it's the ONLY thing this thread does
        if quitting:
            break

def handle_go(pos, limits):
    global worker
    stop_flag.clear()
    worker = threading.Thread(
        target=run_search, args=(pos.copy(), limits, stop_flag), daemon=True
    )
    worker.start()

def handle_stop():
    stop_flag.set()   # worker checks this every ~1024-2048 nodes / each root move

def handle_quit():
    stop_flag.set()
    if worker is not None:
        worker.join(timeout=2.0)   # bounded — never deadlock (UCI-10)
    sys.exit(0)
```

Important correctness notes for the planner:
- The main thread's blocking `for line in sys.stdin` is **not** a violation of
  "non-blocking" — UCI-12's requirement is that `stop`/`quit` are always
  *readable*, and they are, because the main thread never does search work
  itself. The thing that must not block is the *worker*, which must check
  `stop_flag` frequently.
- `go infinite` (D-16): the worker still runs the fixed-depth negamax to
  completion (it has no ID loop to hold "infinitely"), then — instead of
  returning immediately — blocks on `stop_flag.wait()` before emitting
  `bestmove`. The reader thread must remain responsive to `stop` the whole
  time (it already is, since it's a separate thread).
- Poll granularity (D-13 says "every ~1024–2048 nodes and at each root move"):
  checking `Event.is_set()` is cheap but not free at very high node rates;
  Phase 1's pure-Python fixed-depth negamax at shallow depth won't approach
  node counts where this matters, so the exact interval is low-risk
  (Claude's Discretion per CONTEXT.md).
- `readyok` must be emitted from the **main/reader thread**, never after
  waiting on the worker — this is what makes UCI-02 ("never blocks") true even
  while a search is in flight.

### Pattern 4: Fixed-depth negamax substrate (no alpha-beta yet)

`[ASSUMED — standard negamax structure, deliberately simplified per D-01; cross-checked against project PITFALLS.md Pitfall 8 for terminal scoring]`

```python
MATE = 30000   # sentinel; Phase 2/3 will need this constant again for TT ply-adjustment — pick once, document it

def negamax(pos, depth, stop_flag) -> int:
    if stop_flag.is_set():
        raise SearchAborted()
    moves = list(pos.legal_moves())
    if not moves:
        return -(MATE) if pos.is_check() else 0   # checkmate vs stalemate (ply omitted at this shallow, fixed-depth stage — see Open Questions)
    if depth == 0:
        return evaluator.evaluate(pos)             # THE SEAM
    best = -MATE - 1
    for move in moves:
        pos.push(move)
        score = -negamax(pos, depth - 1, stop_flag)
        pos.pop()
        best = max(best, score)
    return best

def search_root(pos, depth, limits, stop_flag) -> Move:
    moves = list(pos.legal_moves())
    if not moves:
        return None   # -> "bestmove (none)", D-12
    best_moves = []
    best_score = -MATE - 1
    for move in moves:
        if stop_flag.is_set():
            break                      # D-03: return best-so-far
        pos.push(move)
        try:
            score = -negamax(pos, depth - 1, stop_flag)
        except SearchAborted:
            pos.pop()
            break
        pos.pop()
        if score > best_score:
            best_score, best_moves = score, [move]
        elif score == best_score:
            best_moves.append(move)   # D-04: collect ties
    return rng.choice(best_moves) if best_moves else moves[0]  # seedable RNG per D-04
```

Notes for the planner:
- **No mate-ply adjustment needed yet.** The `±(MATE − ply)` refinement in
  D-00a matters once mate scores propagate through multiple plies and get
  compared/stored (Phase 2's iterative deepening + TT). At fixed shallow depth
  with no TT, a flat `-MATE`/`0` terminal score is sufficient for Phase 1's
  negamax to correctly prefer/avoid mate — but the **`evaluate()` function
  itself** should already return scores in a range that composes correctly if
  Phase 2 later threads `ply` through; document this as a known simplification,
  not a shortcut that breaks the seam contract (EVAL-01 talks about the
  *evaluator's* mate scoring, not the search's internal terminal check).
- **`go movetime <ms>` / deadline:** wrap `search_root` with a deadline check
  inside the per-root-move loop (`if time.monotonic() > deadline: stop_flag.set(); break`)
  — same mechanism as the external `stop` command, just self-triggered.
- **Bare `go` (D-02):** pick a **default depth** — pure-Python negamax without
  alpha-beta has branching factor ~35, so nodes ≈ 35^depth. Depth 3 ≈ 43k
  leaves, depth 4 ≈ 1.5M leaves. On modern Apple Silicon, a Python leaf-eval
  loop doing ~200k-2M simple evaluations/sec is plausible depending on eval
  cost; **depth 3** is the safer well-under-a-second default with the full
  handcrafted eval (mobility term adds a legal-move-count call per leaf,
  which is real but bounded); **depth 4** may already approach or exceed a
  second once the D-06 mobility/pawn-structure terms are added. The planner
  should benchmark early and treat "depth 3, tunable via a constant" as the
  starting assumption rather than a locked number (this matches D-02's
  "planner may tune").
- **Zero-legal-move `go`:** `search_root` returns `None` immediately — UCI
  layer converts that to `bestmove (none)` and must still respond promptly
  (no full-depth search attempted on a position with zero legal moves).

### Pattern 5: The Evaluator seam (unchanged from project ARCHITECTURE.md)

`[CITED: .planning/research/ARCHITECTURE.md Pattern 1 — reused verbatim, this is the phase's central contract]`

```python
# ance/eval/base.py
from typing import Protocol

class Evaluator(Protocol):
    def evaluate(self, pos) -> int:
        """Centipawns, side-to-move relative (+ = stm better). Mate as ±(MATE-ply)."""
        ...
```

`HandcraftedEval` is the only concrete implementation this phase builds. The
seam is proven "real" (not cosmetic, per project Anti-Pattern 3) if a second,
trivial `Evaluator` (e.g., material-only) can be swapped in via one line in
`main.py`/wiring code with zero changes to `search/negamax.py` — write a test
for exactly this (see Validation Architecture).

### Anti-Patterns to Avoid

- **Diffing the previous `position` command's move list instead of rebuilding
  from scratch** — always construct `chess.Board()` or `chess.Board(fen)` fresh
  and replay `moves` in order (project PITFALLS.md Pitfall 3).
- **Doing search work on the main/reader thread** — breaks UCI-02/UCI-12
  immediately (project PITFALLS.md Pitfall 1).
- **Forgetting `flush=True` / relying on TTY behavior** — works interactively,
  hangs when piped by a real GUI (project PITFALLS.md Pitfall 2).
- **Catching only `chess.IllegalMoveError` and missing `InvalidMoveError`** —
  both occur for different malformed-input shapes (bad syntax vs. illegal-in-
  position); catch `ValueError` (their common base) at the `position`-command
  boundary for a single robust handler, or catch both explicitly for
  distinguishable `info string` wording.
- **Sharing one `chess.Board` between the UCI thread and the search worker** —
  not thread-safe; always `pos.copy()` before handing to the worker.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UCI move syntax parsing (promotions, castling, null moves) | A regex/string-split UCI move parser | `chess.Move.from_uci()` / `board.push_uci()` | Handles `e7e8q`, `e1g1`, `0000`, and raises the correct typed exceptions — hand-rolling reproduces known bug classes (project PITFALLS.md Pitfall 3) |
| Legal move generation, check/checkmate/stalemate detection | Custom movegen | `chess.Board.legal_moves`, `is_checkmate()`, `is_stalemate()` | Exhaustively correct, pure-Python, zero compiled deps — reinventing this is pure risk for zero benefit (project D-00c, PROJECT.md) |
| FEN parsing/validation | A hand-written FEN string splitter | `chess.Board(fen)` / `set_fen()` | Raises `ValueError` on the many ways a FEN can be malformed (row count, castling rights, en passant square); this is exactly the exception D-10 needs |
| Threading primitives for cancellation | Polling a global boolean without synchronization, or a `Queue`-based signal for a single stop flag | `threading.Event` | Purpose-built, GIL-safe, blocking `.wait()` available for D-16's `go infinite` idle |

**Key insight:** Every "don't hand-roll" item here is already the project's
own committed decision (D-00c, python-chess for everything board-related).
The only genuinely custom code in Phase 1 is the UCI I/O loop itself (by
design — that's the one piece python-chess deliberately doesn't provide,
since `chess.engine`/`chess.uci` are client-side modules) and the fixed-depth
negamax + handcrafted eval (also intentional — these are the project's
learning-and-strength core, not solved-problem plumbing).

## Common Pitfalls

All Phase 1-relevant pitfalls are already catalogued in
`.planning/research/PITFALLS.md` (Pitfalls 1–4, 8 map to M1/M1-adjacent) —
this section adds Phase-1-specific sharpening beyond that file rather than
repeating it.

### Pitfall: Treating `bestmove (none)` as optional in "obviously drawn/mated" test positions

**What goes wrong:** A test harness or manual check assumes the engine can
skip responding when there's clearly no move (e.g., "why would it search a
checkmated position") and the `go` handler short-circuits before ever calling
into the UCI response layer, silently dropping the required `bestmove` line.
**Why it happens:** The zero-legal-moves case is a genuine edge case that's
easy to special-case incorrectly rather than route through the same
"always emit exactly one bestmove" code path as every other `go`.
**How to avoid:** Make `search_root` return `None` on zero legal moves (see
Pattern 4) and make the **UCI response layer** — not the search layer — the
single place that decides `None -> "bestmove (none)"` vs `move -> "bestmove <uci>"`.
This guarantees the invariant holds even if search logic changes later.
**Warning signs:** A piped `position fen <checkmate-fen>\ngo\n` script hangs or
prints nothing.

### Pitfall: `go` param parsing that crashes on unimplemented clock/nodes params

**What goes wrong:** `go wtime 300000 btime 300000 winc 0 binc 0` (a real GUI
will very likely send this even in Phase 1, before Phase 3 implements clock
handling) hits a parser that only recognizes `depth`/`movetime`/`infinite` and
raises on the unknown tokens, crashing the command dispatch.
**Why it happens:** UCI-07 only requires *honoring* `movetime`/`depth` this
phase, but the parser must still **accept** the full `go` grammar (D-11:
unknown/unsupported → silently ignored, not crash-worthy) since `wtime/btime`
are real spec tokens, not garbage input.
**How to avoid:** Parse all documented `go` sub-parameters into a typed
struct; params not yet acted upon (`wtime`, `btime`, `winc`, `binc`, `nodes`,
`ponder`, `searchmoves`) are parsed-and-ignored, not rejected. Only fall back
to D-11's "skip unknown leading token" behavior for genuinely unrecognized
tokens outside the UCI grammar.
**Warning signs:** Engine works with a hand-typed pipe script (`go depth 3`)
but crashes or hangs the instant Cute Chess/Arena is used (they always send
`wtime/btime`).

### Pitfall: Confusing "reject and keep board" (D-10) with "reject and reset board"

**What goes wrong:** On a malformed `position fen ...`, the handler
accidentally calls `board.reset()` or constructs a fresh empty board "to be
safe," destroying whatever valid position was previously in play.
**Why it happens:** The exception-handling code path is naturally adjacent to
board-construction code, making an accidental reset an easy copy-paste error.
**How to avoid:** Structure the handler so the exception is caught **before**
any assignment to the live `Position`/`Board` reference — build the candidate
board in a local variable first, and only swap it into the live state on
success. On failure, the local variable is simply discarded.
**Warning signs:** A test that sends a valid `position`, then a malformed one,
then `go` — and asserts the `go` still operates on the *first* (valid)
position — fails.

## Code Examples

### UCI handshake response (verified format)

```python
# Source: gist.github.com/DOBRO/2592c6dad754ba67e6dcaec8c90165bf (D-08 fills in the literal strings)
def handle_uci():
    print("id name ANCE 0.1", flush=True)
    print("id author Lasse Siemoneit", flush=True)
    # zero `option` lines per D-09
    print("uciok", flush=True)

def handle_isready():
    print("readyok", flush=True)   # from the reader thread; never gated behind search
```

### Malformed FEN / illegal move handling (D-10)

```python
# Source: Context7 /niklasf/python-chess v1.11.2 (verified this session)
import chess

def handle_position(tokens, current_board):
    candidate = chess.Board() if tokens[0] == "startpos" else None
    if tokens[0] == "fen":
        fen = " ".join(tokens[1:7])  # FEN is 6 space-separated fields
        try:
            candidate = chess.Board(fen)
        except ValueError as e:
            emit_info_string(f"invalid fen, ignoring position command: {e}")
            return current_board   # D-10: keep previous board untouched
    if "moves" in tokens:
        move_tokens = tokens[tokens.index("moves") + 1:]
        for m in move_tokens:
            try:
                candidate.push_uci(m)
            except ValueError as e:   # covers both InvalidMoveError and IllegalMoveError
                emit_info_string(f"invalid/illegal move '{m}' in position command, ignoring: {e}")
                return current_board  # D-10: keep previous board untouched, don't apply partial moves
    return candidate
```

### Terminal / zero-legal-move detection (D-12, SRCH-01)

```python
# Source: Context7 /niklasf/python-chess v1.11.2
def has_no_legal_moves(board) -> bool:
    return board.is_checkmate() or board.is_stalemate() or not any(board.legal_moves)
    # is_game_over() also covers insufficient material / 75-move / fivefold-repetition auto-draws;
    # for D-12's "zero legal moves -> bestmove (none)" check specifically, checkmate/stalemate
    # are the two reachable-by-move-sequence cases; is_game_over() is the safe general check.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `Move.from_uci()` raising bare `IndexError` on malformed input | Raises `ValueError` | Pre-1.11.2 python-chess release | Consistent exception hierarchy — catch `ValueError` everywhere for malformed chess input, not a mix of `IndexError`/`ValueError` |
| Generic exceptions for all move problems | Typed `chess.InvalidMoveError` / `chess.IllegalMoveError` (both `ValueError` subclasses) | Current python-chess (confirmed present in 1.11.2 changelog) | Lets D-10's handler distinguish "bad syntax" from "illegal here" in the `info string` wording if desired, while still allowing a single `except ValueError` catch-all |
| Stockfish internal eval == UCI-reported `score cp` | Stockfish normalizes UCI `score cp` output (not 1:1 with internal eval) since SF12+ | SF12 (documented in project PITFALLS.md) | **Not directly relevant to Phase 1** (no Stockfish integration yet) but flagged so the planner doesn't assume Phase-1 handcrafted `score cp` needs to match Stockfish's scale — it doesn't; only the *move quality* is compared later via gauntlet, not raw score values |

**Deprecated/outdated:** None specific to Phase 1's scope — the UCI protocol
itself has been stable since 2000 with no breaking changes relevant here.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Default search depth of 3 (tunable) keeps a bare `go` well under a second with the full D-06 eval terms included | Pattern 4 (Negamax Substrate) | Low — if wrong, the planner benchmarks and adjusts a single constant; D-02 explicitly permits tuning |
| A2 | The exact non-blocking threading idiom (blocking `readline()` on main + daemon worker + `Event`) is *the* correct shape for this project, not just *a* correct shape | Pattern 3 (Threading Model) | Low — this is a widely-used, low-risk pattern corroborated by the project's own PITFALLS.md Pitfall 1/2; alternative shapes (asyncio, select-based I/O) would also satisfy UCI-12 but add complexity with no documented benefit here |
| A3 | `is_checkmate()`/`is_stalemate()` cover all reachable zero-legal-move states for D-12's purposes in Phase 1 (i.e., `is_game_over()`'s other draw conditions — insufficient material, 75-move, fivefold — are not reachable as "zero legal moves" cases, they're separate terminal conditions with moves still available in principle) | Code Examples — Terminal detection | Low-Medium — if a GUI ever sends a `position` already at e.g. insufficient-material with moves still technically legal, `go` should still search and return a real move, not `(none)`; using `is_checkmate() or is_stalemate()` (not full `is_game_over()`) for the `(none)` decision avoids over-triggering `(none)` on non-zero-legal-move draws |
| A4 | Poll interval of 1024–2048 nodes (D-13) is fine at Phase 1's shallow fixed depths without measurable `stop` latency | Pattern 3 (Threading Model) | Low — Phase 1 has no deep search; the constraint matters more once Phase 2/3 add real depth. Not urgent to get exactly right now. |

**If this table is empty:** N/A — see entries above. All four are LOW risk;
none block planning.

## Open Questions

1. **Exact default search depth (D-02) for a bare `go`.**
   - What we know: negamax branching factor ~35 without pruning; depth 3 ≈
     43k leaves is safely sub-second even with a real eval; depth 4 ≈ 1.5M
     leaves may or may not be, depending on per-leaf eval cost (mobility term
     calls `legal_moves` again at each leaf).
   - What's unclear: actual wall-clock cost of the full D-05/D-06 handcrafted
     eval per leaf on the target M4 hardware — not measured this session (no
     code exists yet to benchmark).
   - Recommendation: planner picks depth 3 as the starting default, adds a
     one-line comment noting it's benchmarked/tunable, and the plan should
     include an explicit "measure nodes/sec and confirm sub-second bare `go`"
     verification step rather than trusting the estimate blind.

2. **Whether `go` clock params (`wtime`/`btime`/`winc`/`binc`) need to be
   *parsed* (not acted on) in Phase 1, given UCI-08 (full clock handling) is
   explicitly Phase 3 scope.**
   - What we know: D-01/UCI-07 only requires honoring `movetime`/`depth`;
     UCI-08 (Phase 3) requires computing a time budget from clock params.
   - What's unclear: whether CONTEXT.md's "silently ignore" (D-11) intends
     clock params to be full grammar-parsed-and-discarded now, or genuinely
     untouched until Phase 3.
   - Recommendation: parse them now (see the `go`-crash pitfall above) since
     real GUIs send them unconditionally — refusing to parse a spec-legal
     token would violate D-11's spirit ("don't crash on things you don't yet
     act on") even though D-11's literal wording is about *unknown* tokens.
     This is a request for the planner/discuss-phase to confirm if ambiguous.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 (native arm64) | Runtime (CLAUDE.md pin) | ✗ (not installed) | — | Python 3.13.14 and 3.14.6 are installed via Homebrew (arm64, confirmed native) — both satisfy the project's "3.12+" constraint; use 3.13 as the venv interpreter unless a specific 3.12-only need surfaces |
| `chess` (python-chess) | Board/UCI plumbing (all requirements) | ✗ (not yet installed — greenfield repo, no venv exists) | 1.11.2 available on PyPI | None needed — install as part of Wave 0 |
| `pytest` | TOOL-01/02, all UCI/eval tests | ✗ (not yet installed) | 8.4.2 available on PyPI | None needed — install as part of Wave 0 |
| git | Version control | ✓ | 2.50.1 | — |
| Stockfish | TOOL-01 (GUI validation is manual, doesn't strictly need Stockfish) — used later for Phase 4 labeling, not Phase 1 | ✗ | — | Not required for Phase 1 automated work; `brew install stockfish` if a human wants a sparring partner during manual GUI validation |
| Cute Chess / Arena (GUI) | TOOL-01 — "loads and plays a full legal game in a GUI" | ✗ | — | This is inherently a manual/human verification step (see Validation Architecture) — flag as a `checkpoint:human-verify` task requiring the human to download Cute Chess (prebuilt macOS binary, no build needed) or Arena before that specific step; does not block automated implementation/testing |

**Missing dependencies with no fallback:** None — every gap above has a
clear, low-friction resolution (install via `pip`/`brew`, or is inherently a
manual human step already expected by TOOL-01's nature).

**Missing dependencies with fallback:**
- Python 3.12 → use 3.13 (already installed, arm64, satisfies "3.12+")
- `chess`, `pytest` → install in Wave 0 (see Package Legitimacy Audit)
- Stockfish, Cute Chess/Arena → not needed for automated Phase 1 work; needed
  only for the manual GUI-validation success criterion (human installs when
  reaching that checkpoint)

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 (not yet installed — Wave 0) |
| Config file | none yet — Wave 0 creates `pyproject.toml [tool.pytest.ini_options]` or `pytest.ini` with `testpaths = ["tests"]` |
| Quick run command | `pytest tests/ -x -q -m "not slow"` |
| Full suite command | `pytest tests/ -q` (includes the `@pytest.mark.slow` 100-game random-mover gauntlet) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UCI-01 | `uci` → id/uciok handshake | integration (subprocess) | `pytest tests/test_uci_handshake.py::test_uci_command -x` | ❌ Wave 0 |
| UCI-02 | `isready` → `readyok`, never blocks (incl. sent before any other command) | integration | `pytest tests/test_uci_handshake.py::test_isready_before_anything -x` | ❌ Wave 0 |
| UCI-03 | `ucinewgame` resets per-game state (no-op M1, board resets) | integration | `pytest tests/test_uci_handshake.py::test_ucinewgame_resets -x` | ❌ Wave 0 |
| UCI-04 | `position startpos moves ...` sets board correctly | unit (Position adapter) + integration | `pytest tests/test_position_command.py::test_startpos_with_moves -x` | ❌ Wave 0 |
| UCI-05 | Malformed `position fen ...` rejected, board unchanged, no crash | unit + integration | `pytest tests/test_position_command.py::test_malformed_fen_rejected -x` | ❌ Wave 0 |
| UCI-06 | Every `go` variant yields exactly one legal `bestmove`, incl. mate/stalemate | integration (parametrized over `go` variants + terminal FENs) | `pytest tests/test_go_bestmove.py -x` | ❌ Wave 0 |
| UCI-07 | `go depth <n>` / `go movetime <ms>` honored | integration (timing/depth assertion) | `pytest tests/test_go_bestmove.py::test_depth_and_movetime -x` | ❌ Wave 0 |
| UCI-09 | `stop` ends search promptly with a `bestmove` | integration (send `go infinite` then `stop`, assert response within ~1s) | `pytest tests/test_go_bestmove.py::test_stop_is_prompt -x` | ❌ Wave 0 |
| UCI-10 | `quit` exits cleanly even mid-search, never deadlocks | integration (send `go infinite` then `quit`, assert process exits within timeout) | `pytest tests/test_go_bestmove.py::test_quit_never_deadlocks -x` | ❌ Wave 0 |
| UCI-12 | stdin stays readable during search (non-blocking) | integration (same as UCI-09/10 — these ARE the non-blocking proof) | covered by `test_stop_is_prompt`, `test_quit_never_deadlocks` | ❌ Wave 0 |
| SRCH-01 | Only legal moves generated; checkmate/stalemate/draw detection | unit (Position adapter against known FENs) | `pytest tests/test_position_command.py::test_terminal_detection -x` | ❌ Wave 0 |
| EVAL-01 | `evaluate()` stm-relative; swap seam changes only eval | unit (symmetry test + swap test) | `pytest tests/test_eval_seam.py::test_symmetric_position_scores_zero`, `::test_evaluator_swap_changes_only_eval` | ❌ Wave 0 |
| EVAL-02 | Handcrafted eval matches Simplified Eval reference on known positions | unit (spot-check against this RESEARCH.md's tables) | `pytest tests/test_eval_seam.py::test_handcrafted_matches_reference_values -x` | ❌ Wave 0 |
| TOOL-01 | Loads and plays a full legal game in a GUI | **manual** (`checkpoint:human-verify` — GUIs aren't scriptable in this stack) | N/A — human runs Cute Chess/Arena | ❌ Wave 0 (no automation possible) |
| TOOL-02 | Beats a random-mover 100/100 | integration/slow (scripted self-play, python-chess referees) | `pytest tests/test_random_mover_gauntlet.py -x -m slow` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q -m "not slow"` (excludes the
  100-game gauntlet, which is slow but should still run at least once per
  wave)
- **Per wave merge:** `pytest tests/ -q` (full suite, including the
  100-game gauntlet)
- **Phase gate:** Full suite green, including a manual `checkpoint:human-verify`
  for TOOL-01 (GUI load + full game), before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `pip install chess pytest` in a native-arm64 venv (`checkpoint:human-verify`
      per Package Legitimacy Audit — one-time, both packages)
- [ ] `pyproject.toml` or `pytest.ini` with `testpaths = ["tests"]` and a
      `slow` marker registered (`markers = ["slow: 100-game self-play gauntlet"]`)
- [ ] `tests/conftest.py` — a fixture that spawns
      `subprocess.Popen([sys.executable, "-m", "ance"], stdin=PIPE, stdout=PIPE, text=True, bufsize=1)`,
      writes commands with `flush=True`, and reads lines until a sentinel
      (`uciok`/`readyok`/`bestmove ...`) with a bounded timeout (avoid an
      unbounded `readline()` hanging the test suite itself if the engine has a
      bug — use `select`/a reader thread with `queue.Queue` inside the test
      fixture, or a subprocess-level timeout)
- [ ] `tests/test_uci_handshake.py`, `test_position_command.py`,
      `test_go_bestmove.py`, `test_eval_seam.py`,
      `test_random_mover_gauntlet.py` — all net new
- [ ] `ance/tools/random_mover_gauntlet.py` — the actual harness the slow test
      imports/drives (random mover: uniformly pick from `board.legal_moves`
      with a seeded RNG; referee game-over via python-chess; assert ANCE wins
      or draws 100/100 against it, per TOOL-02's literal "beats" — clarify
      with discuss-phase/planner whether a draw counts as *not* beating; a
      correct engine with a full eval should not need to rely on draws
      against a uniformly-random opponent)

*(All of the above are new — this is a greenfield repo with zero existing test
infrastructure.)*

## Security Domain

This phase has no network surface, no user-facing auth, and no persistence —
ANCE reads UCI commands from stdin (a local pipe from a GUI or test harness)
and writes to stdout. Most ASVS categories are not applicable to a local UCI
engine reading local process input.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user identity concept in a local UCI engine |
| V3 Session Management | No | No sessions — stdin/stdout process lifetime only |
| V4 Access Control | No | No multi-user/permission model |
| V5 Input Validation | **Yes** | Every `position fen ...` / `moves ...` token is untrusted input from stdin — validated exclusively via `python-chess`'s `ValueError`/`InvalidMoveError`/`IllegalMoveError` exceptions (Pattern 2); never `eval()`/`exec()` any input; unknown UCI tokens are ignored, not executed (D-11) |
| V6 Cryptography | No | No secrets, no crypto in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/adversarial FEN or UCI move string crashing the engine (denial of service against a running GUI match) | Denial of Service | Catch `ValueError` (and subclasses) at every parse boundary per Pattern 2; never let a bad `position`/`go` command propagate an unhandled exception past the command dispatcher — project PITFALLS.md's Security Mistakes table already flags this exact pattern at project level |
| Pathologically long input line on stdin | Denial of Service (resource exhaustion) | Out of scope for Phase 1 — python-chess's own parsing bounds this in practice (a FEN or move list has a natural small upper bound); not a realistic threat from a local GUI/test harness. Noting for completeness, not recommending action this phase. |

No other threat patterns are relevant to this phase's scope (no model-loading,
no network, no filesystem writes beyond normal Python process behavior).

## Sources

### Primary (HIGH confidence)
- Context7 `/niklasf/python-chess` v1.11.2 — Board API, exception hierarchy — python-chess `docs/core.rst`, `README.rst`, `CHANGELOG.rst`/`CHANGELOG-OLD.rst`
- `gist.github.com/DOBRO/2592c6dad754ba67e6dcaec8c90165bf` — canonical UCI protocol command/response wording (fetched directly this session)
- `chessprogramming.org/Simplified_Evaluation_Function` — exact Michniewski piece values and all six piece-square tables (fetched directly this session)
- `chessprogramming.org/UCI` — corroborating UCI protocol overview
- `pip3 index versions chess` / `pip3 index versions pytest` — live PyPI registry version confirmation (this session)

### Secondary (MEDIUM confidence)
- `github.com/niklasf/python-chess` issues #800, #369 — `IllegalMoveError`/`InvalidMoveError`/`ValueError` hierarchy, cross-checked via WebSearch against the Context7 docs
- `talkchess.com` UCI nullmove thread — corroborates the `bestmove (none)`/`bestmove 0000` convention ambiguity

### Tertiary (LOW confidence)
- General WebSearch results on Python non-blocking stdin/threading patterns for UCI engines — no single canonical source exists for this idiom; cross-checked against the project's own (already HIGH-confidence) `.planning/research/PITFALLS.md` Pitfall 1/2 for corroboration
- General WebSearch results on pytest + subprocess UCI testing patterns — community convention, not a documented spec

### Project-level (already HIGH confidence, reused verbatim)
- `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` — this phase builds on, not duplicates, that research

## Appendix: Simplified Evaluation Function Tables (pinned)

**Source:** `https://www.chessprogramming.org/Simplified_Evaluation_Function`
(Tomasz Michniewski), fetched directly this session (2026-07-05) via
WebFetch and cross-checked against the well-known published values. This
appendix is the single in-repo source of truth for D-05/EVAL-02 — Plan
01-04 transcribes from here at execution time, it does NOT re-fetch the
live page.

### Piece values (centipawns)

| Piece | Value |
|-------|-------|
| Pawn | 100 |
| Knight | 320 |
| Bishop | 330 |
| Rook | 500 |
| Queen | 900 |
| King | excluded from `PIECE_VALUES` (D-05/Plan 01-03) — search terminal scoring uses `MATE`, not a king material value |

### Orientation convention (READ BEFORE TRANSCRIBING)

The tables below are reproduced **exactly as chessprogramming.org prints
them**: each table's first printed row is **rank 8**, its last printed
row is **rank 1**, and within each row the columns run **a-file to
h-file** (the standard "looking at the board from White's side, rank 8
at the top" diagram convention).

`ance/eval/tables.py` stores each table as a flat 64-tuple indexed with
python-chess's `chess.square(file, rank)` convention, where index `0` =
a1, index `7` = h1, index `56` = a8, index `63` = h8 (rank index `0` =
rank 1, increasing upward). **This is the opposite row order from how
the tables are printed below** — to transcribe correctly, reverse the
row order: the table's printed **last** row (rank 1) becomes tuple
indices `0..7`, and its printed **first** row (rank 8) becomes tuple
indices `56..63`. Getting this reversal backwards is the single most
likely transcription error, and it will NOT be caught by a
64-entries-and-zero-back-ranks structural check alone (the pawn table's
rank 1 and rank 8 rows are both zero either way) — see "Pinned reference
cells" below, chosen specifically because they differ between the top
and bottom rows and will fail loudly if reversed.

Black's lookup for the same physical square is
`TABLE[chess.square_mirror(square)]` — standard PST-mirroring, applied
in `ance/eval/handcrafted.py` (Plan 01-04 Task 2), not in `tables.py`
itself.

### Pawn (`PAWN_PST`)

Printed rank 8 (top) → rank 1 (bottom), a-file → h-file:

```
 0,  0,  0,  0,  0,  0,  0,  0
50, 50, 50, 50, 50, 50, 50, 50
10, 10, 20, 30, 30, 20, 10, 10
 5,  5, 10, 25, 25, 10,  5,  5
 0,  0,  0, 20, 20,  0,  0,  0
 5, -5,-10,  0,  0,-10, -5,  5
 5, 10, 10,-20,-20, 10, 10,  5
 0,  0,  0,  0,  0,  0,  0,  0
```

### Knight (`KNIGHT_PST`)

```
-50,-40,-30,-30,-30,-30,-40,-50
-40,-20,  0,  0,  0,  0,-20,-40
-30,  0, 10, 15, 15, 10,  0,-30
-30,  5, 15, 20, 20, 15,  5,-30
-30,  0, 15, 20, 20, 15,  0,-30
-30,  5, 10, 15, 15, 10,  5,-30
-40,-20,  0,  5,  5,  0,-20,-40
-50,-40,-30,-30,-30,-30,-40,-50
```

### Bishop (`BISHOP_PST`)

```
-20,-10,-10,-10,-10,-10,-10,-20
-10,  0,  0,  0,  0,  0,  0,-10
-10,  0,  5, 10, 10,  5,  0,-10
-10,  5,  5, 10, 10,  5,  5,-10
-10,  0, 10, 10, 10, 10,  0,-10
-10, 10, 10, 10, 10, 10, 10,-10
-10,  5,  0,  0,  0,  0,  5,-10
-20,-10,-10,-10,-10,-10,-10,-20
```

### Rook (`ROOK_PST`)

```
 0,  0,  0,  0,  0,  0,  0,  0
 5, 10, 10, 10, 10, 10, 10,  5
-5,  0,  0,  0,  0,  0,  0, -5
-5,  0,  0,  0,  0,  0,  0, -5
-5,  0,  0,  0,  0,  0,  0, -5
-5,  0,  0,  0,  0,  0,  0, -5
-5,  0,  0,  0,  0,  0,  0, -5
 0,  0,  0,  5,  5,  0,  0,  0
```

### Queen (`QUEEN_PST`)

```
-20,-10,-10, -5, -5,-10,-10,-20
-10,  0,  0,  0,  0,  0,  0,-10
-10,  0,  5,  5,  5,  5,  0,-10
 -5,  0,  5,  5,  5,  5,  0, -5
  0,  0,  5,  5,  5,  5,  0, -5
-10,  5,  5,  5,  5,  5,  0,-10
-10,  0,  5,  0,  0,  0,  0,-10
-20,-10,-10, -5, -5,-10,-10,-20
```

### King, middlegame (`KING_MG_PST`)

```
-30,-40,-40,-50,-50,-40,-40,-30
-30,-40,-40,-50,-50,-40,-40,-30
-30,-40,-40,-50,-50,-40,-40,-30
-30,-40,-40,-50,-50,-40,-40,-30
-20,-30,-30,-40,-40,-30,-30,-20
-10,-20,-20,-20,-20,-20,-20,-10
 20, 20,  0,  0,  0,  0, 20, 20
 20, 30, 10,  0,  0, 10, 30, 20
```

### King, endgame (`KING_EG_PST`)

```
-50,-40,-30,-20,-20,-30,-40,-50
-30,-20,-10,  0,  0,-10,-20,-30
-30,-10, 20, 30, 30, 20,-10,-30
-30,-10, 30, 40, 40, 30,-10,-30
-30,-10, 30, 40, 40, 30,-10,-30
-30,-10, 20, 30, 30, 20,-10,-30
-30,-30,  0,  0,  0,  0,-30,-30
-50,-30,-30,-30,-30,-30,-30,-50
```

### Pinned reference cells (for Plan 01-04 Task 1's transcription test)

After correct transcription into `chess.square()`-indexed tuples, these
cells MUST hold exactly these values. Each was chosen because it differs
from its vertically-mirrored counterpart, so a reversed-row transcription
error fails loudly instead of silently passing a merely-structural check:

| Cell(s) | Table | Expected value |
|---------|-------|-----------------|
| d4, e4 | `PAWN_PST` | `20` |
| d2, e2 | `PAWN_PST` | `-20` |
| d7, e7 | `PAWN_PST` | `50` |
| a1, h1, a8, h8 | `KNIGHT_PST` | `-50` |
| d4, e4, d5, e5 | `KING_EG_PST` | `40` |
| b1 | `KING_EG_PST` | `-30` |
| b8 | `KING_EG_PST` | `-40` |

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; both `chess` and `pytest` versions verified live against PyPI this session
- Architecture: HIGH — this phase's architecture is a strict, already-researched subset of `.planning/research/ARCHITECTURE.md`; no new architectural risk introduced
- UCI protocol contract: HIGH — fetched directly from the canonical spec source and cross-checked against chessprogramming.org
- python-chess exception semantics: HIGH — confirmed via Context7 official docs + GitHub issue corroboration
- Handcrafted eval tables: HIGH — fetched directly from chessprogramming.org, byte-for-byte reproduction of the well-known reference values
- Threading model: MEDIUM — sound, low-risk, widely-used pattern, but not a single canonical documented spec (flagged honestly rather than overstated)
- Pitfalls: HIGH — this phase's pitfalls are a proper subset of the already-HIGH-confidence project-level `PITFALLS.md`, plus 3 Phase-1-specific sharpenings added this session

**Research date:** 2026-07-05
**Valid until:** UCI protocol and python-chess's core exception API are stable/slow-moving — 90 days is a safe revalidation window. Re-check `pip3 index versions chess`/`pytest` if planning is delayed more than a few weeks (both ecosystems release patches frequently, though breaking changes to the APIs used here are unlikely).
