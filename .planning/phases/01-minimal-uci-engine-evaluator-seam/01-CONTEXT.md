# Phase 1: Minimal UCI Engine & Evaluator Seam - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning

<domain>
## Phase Boundary

A GUI-playable UCI engine that **never hangs**, routes every leaf through a
swappable `evaluate(position) -> centipawns` seam (side-to-move relative), and
plays a full legal game with a handcrafted evaluator — beating a random mover
100/100.

**In scope:** the hand-written non-blocking UCI stdin/stdout loop; a minimal
fixed-depth negamax that exercises the eval seam; the handcrafted eval; board
plumbing via `python-chess`; malformed-input robustness.

**Out of scope (later phases — do NOT build here):** fail-soft alpha-beta,
iterative deepening, quiescence (Phase 2); `info depth … pv …` search output
(Phase 2, UCI-11); transposition table, move ordering, `wtime/btime` clock
control (Phase 3); NNUE eval and training (Phases 4–5); `setoption` handling,
tapered eval (v2). See `.planning/REQUIREMENTS.md` "Out of Scope".
</domain>

<decisions>
## Implementation Decisions

### Locked upstream (carried forward — do NOT re-open)
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

### Move selection ("search" substrate before Phase 2)
- **D-01:** Phase 1 uses a **minimal fixed-depth negamax** — NO alpha-beta
  pruning, NO quiescence, NO iterative deepening. It honors `go depth <n>` and
  `go movetime <ms>` for real and evaluates every leaf through the seam. Phase 2
  bolts alpha-beta + ID + quiescence onto this skeleton (this is the substrate,
  not scope creep — UCI-07 requires depth handling in Phase 1).
- **D-02:** A bare `go` (no depth/movetime/clock) searches to a **fixed default
  depth** (choose a value that completes in well under a second in pure Python,
  ~3–4 to start; the planner may tune). Fully deterministic and always terminates.
- **D-03:** `go movetime <ms>` and `stop` **abort and return the best root move
  found so far** (root-level best tracking, since there is no ID yet).
- **D-04:** On tied eval scores, pick **uniformly at random among all equal-best
  moves**, using a **seedable RNG** (fixed seed in tests for reproducibility).
  Avoids deterministic move-shuffle loops and varies games vs the random mover.

### Handcrafted eval
- **D-05:** Base on the **Simplified Evaluation Function** (Tomasz Michniewski):
  piece values P=100, N=320, B=330, R=500, Q=900; one single-phase PST per piece;
  plus its two king tables (middlegame vs endgame) selected by a discrete
  material-count phase check (**not** tapering).
- **D-06:** Add these cheap, symmetric positional terms on top of material+PST:
  **mobility** (side-to-move legal-move-count difference), **bishop pair** bonus,
  **tempo** bonus (side to move), and **pawn-structure penalties** (doubled +
  isolated pawns).
- **D-07:** All eval terms are **symmetric and side-to-move relative** per the
  D-00a seam contract.
- ⚠ **Tradeoff acknowledged (user's deliberate call):** a richer handcrafted
  baseline raises the bar for the Phase 5 "NNUE beats handcrafted" Elo-gain proof.
  Accepted as a more honest baseline.

### Identity & options
- **D-08:** `id name ANCE 0.1` (version bumped per milestone — shows up in Cute
  Chess / gauntlet logs to distinguish builds), `id author Lasse Siemoneit`.
- **D-09:** Declare **zero `option` lines** in M1 (emit only id + `uciok`).
  Accept any `setoption` command **silently without crashing** (forward-compatible;
  real handling deferred to v2 / CFG-01).

### Robustness & error handling
- **D-10:** `position fen <malformed>` or an illegal move in a `moves` list →
  **reject the command and keep the current board untouched**, emitting an
  `info string` noting the error. A later valid `position` recovers cleanly.
  Never crash. *(success criterion 5, UCI-05)*
- **D-11:** Unknown/unsupported commands → **silently ignored** per the UCI spec
  (skip the unknown leading token, attempt to parse the rest of the line).
- **D-12:** `go` in a **zero-legal-move position** (checkmate/stalemate) →
  emit **`bestmove (none)`** (Stockfish convention; matches SF in gauntlet log
  diffs). Must return promptly. *(success criterion 2)*

### Threading & stop mechanism
- **D-13:** A single search worker thread; the reader sets a shared
  **`threading.Event` cancel flag** (plus a deadline) on `stop`/`quit`/timeout.
  The worker checks the flag **every ~1024–2048 nodes and at each root move**,
  aborting to return best-so-far. `quit` sets the flag, lets the worker unwind,
  then exits cleanly (never deadlocks on a running search — UCI-10).
- **D-14:** stdout is flushed on **every line** so `bestmove` and handshake
  responses are never buffered. *(success criterion 2)*

### Launch & entry point
- **D-15:** Ship an **`ance/` package with `__main__.py`**, launched via
  `python -m ance`. Modular layout (uci / search / eval separated) honoring the
  swappable-eval mandate. GUI/gauntlet command = the **arm64 venv python** +
  `-m ance`. No install step required.

### `go infinite`
- **D-16:** `go infinite` searches to the default depth, then **idles holding the
  result until `stop` arrives**, only then emitting `bestmove` (UCI-correct —
  infinite must never self-terminate). The non-blocking reader keeps accepting
  `stop`/`quit` throughout.

### `ucinewgame`
- **D-17:** `ucinewgame` is a **no-op reset of per-game state** in M1 (there is no
  TT/history yet); it may reset the board and reseed the tie-break RNG. Clears
  TT/history starting Phase 2. *(UCI-03)*

### Claude's Discretion
- Exact default search depth value (D-02) — planner tunes to pure-Python speed.
- Internal module/file names and the precise node-count polling interval (D-13).
- Whether the debug channel (D-18 below) also honors an `ANCE_DEBUG` env var in
  addition to UCI `debug on/off`.
- Precise `info string` wording for rejected input.

### Debug logging
- **D-18:** A **stderr-only** diagnostic channel (never stdout — keeps the
  protocol stream clean), **off by default**, toggled on by the UCI `debug on/off`
  command (and optionally an `ANCE_DEBUG` env var). Insurance for diagnosing
  GUI handshake / silent-hang issues.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope, requirements & locked decisions
- `.planning/ROADMAP.md` §"Phase 1: Minimal UCI Engine & Evaluator Seam" — goal,
  success criteria, and the mapped requirements; also the roadmap-locked
  threading + eval-seam decisions (D-00a/b).
- `.planning/REQUIREMENTS.md` — full text of UCI-01…07, UCI-09, UCI-10, UCI-12,
  SRCH-01, EVAL-01, EVAL-02, TOOL-01, TOOL-02, plus the "Out of Scope" table
  that bounds this phase.
- `.planning/PROJECT.md` — Core Value, constraints (Python 3.12+, native arm64,
  swappable-eval architecture boundary), and Key Decisions table.

### Tech stack & platform constraints
- `.claude/CLAUDE.md` §"Technology Stack" — `python-chess` 1.11.2 (import name
  `chess`; use for the board, NOT the UCI loop), Python 3.12 native arm64,
  Stockfish/Cute Chess tooling. §"MPS / M4-Specific Constraints" is Phase 4+ only.

### External references (not in-repo — consult during research/implementation)
- UCI protocol specification — the authoritative command/response contract for
  `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit`, `bestmove`,
  `info`. (Backs D-08…D-17.)
- Simplified Evaluation Function (Tomasz Michniewski, chessprogramming wiki) —
  the piece values, PSTs, and king mid/end tables for D-05.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None yet** — this is the first phase of a greenfield repo. No source code
  exists; only `.planning/` docs and project config.

### Established Patterns
- The project mandates a **swappable evaluation module** (`evaluate(position)->cp`)
  and a search/eval boundary clean enough to later port to a compiled language.
  Phase 1 establishes this seam; every downstream phase depends on it staying
  stable.

### Integration Points
- This phase defines the seam interface (D-00a) that Phase 4/5's NNUE eval will
  implement, and the search skeleton (D-01) that Phase 2/3 will extend. Design
  both as the contract, not throwaway scaffolding.
</code_context>

<specifics>
## Specific Ideas

- Engine name string is literally `ANCE 0.1` (version segment bumped per
  milestone) — the user wants build-distinguishable names in gauntlet/GUI logs.
- Handcrafted eval anchored to the well-known Simplified Evaluation Function so
  values/tables are verifiable against a published reference.
- Terminal-position output matches Stockfish (`bestmove (none)`) specifically so
  Phase 5 gauntlet log diffs against SF line up.
</specifics>

<deferred>
## Deferred Ideas

- **`setoption` / configurable Hash/net-path/threads** — v2 (CFG-01); M1 declares
  zero options and ignores `setoption`.
- **Tapered (midgame/endgame) evaluation** — v2 (EVAL-04); M1 uses the discrete
  Simplified-Eval king-table switch only, not blended tapering.
- **Console-script (`ance`) entry point via pyproject** — considered for launch;
  chose `python -m ance` for M1. Revisit if/when packaging for distribution.
- **Caching/incremental mobility** — the mobility term costs a movegen call per
  leaf; acceptable at Phase-1 depths, worth optimizing when real search arrives.

None of the above are in Phase 1 scope — discussion stayed within the phase
boundary.
</deferred>

---

*Phase: 1-minimal-uci-engine-evaluator-seam*
*Context gathered: 2026-07-05*
