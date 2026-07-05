# Walking Skeleton — ANCE (A Neural-network Chess Engine)

**Phase:** 1 (Minimal UCI Engine & Evaluator Seam)
**Generated:** 2026-07-05
**Implemented by:** Plan 01-01 (`01-01-PLAN.md`)

## Capability Proven End-to-End

A UCI GUI, a Cute Chess/Arena instance, or a piped test script can launch
`python -m ance`, complete the `uci`/`isready` handshake (`id name ANCE 0.1`,
`id author Lasse Siemoneit`, `uciok`, `readyok`), send `go`, and receive
exactly one legal `bestmove` line — computed on a worker thread while the
reader thread stays responsive to `stop`/`quit` — before any real search
algorithm or evaluation function exists. This proves the full
stdin-to-stdout process loop, the non-blocking threading model, and the
package/entry-point shape that every later plan in this phase (and every
later phase in the project) builds on without renegotiating.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.13 (native arm64), venv at `.venv/` | Python 3.12 itself is not installed on this machine; 3.13/3.14 are installed via Homebrew (native arm64, confirmed) and satisfy the project's "3.12+" floor. Never Rosetta/x86 (CLAUDE.md constraint). |
| Board/movegen | `python-chess` (`chess` 1.11.2) behind a narrow `Position` adapter | Project-locked (D-00c); `chess.engine` is never used to speak the protocol — only python-chess's `Board` for legality/FEN/UCI parsing. |
| Protocol I/O | Hand-written UCI stdin/stdout loop (`ance/uci/loop.py`) | D-00c — ANCE *is* the engine; no client-side UCI library can play this role. |
| Threading model | Single reader thread (main) blocks on `sys.stdin`; a daemon worker thread is spawned per `go`; a shared `threading.Event` stop flag is polled by the worker every `NODE_POLL_INTERVAL` node visits and at every root move | D-00b/D-13 — the single hardest-to-retrofit decision in the whole project; established here while the search behind it is still trivial. |
| Evaluator seam | `ance/eval/base.py` — `Evaluator` Protocol, `evaluate(position) -> int` centipawns, side-to-move relative, mate as `±(MATE-ply)` | D-00a/EVAL-01 — the other hardest-to-retrofit decision. Search never imports a concrete evaluator class. |
| Entry point | `python -m ance` (`ance/__main__.py`) | D-15 — no console-script/pyproject entry point this milestone; GUI/gauntlet command is literally `<venv>/bin/python -m ance`. |
| Directory layout | Flat `ance/` package: `uci/`, `board/`, `search/`, `eval/`, `tools/` (no `engine/` wrapper this phase) | Matches 01-RESEARCH.md's Phase-1-scoped structure and CONTEXT.md D-15 literally; later phases may introduce `nnue_format/`/`training/` as new top-level siblings without moving `ance/`. |
| Test harness | pytest 8.x driving the engine as a real subprocess over stdin/stdout pipes (`tests/conftest.py`) | Only realistic way to verify a hand-written protocol loop; unit tests supplement for `Position`/`Evaluator`/search internals. |
| Output discipline | `print(..., flush=True)` on every UCI line | D-14 — stdout is piped by every real GUI; unflushed output is the #1 cause of a "hung" engine (PITFALLS.md Pitfall 2). |

## Stack Touched in Plan 01 (the Walking Skeleton plan)

- [x] Project scaffold — `pyproject.toml` (pytest config, `slow` marker), `.venv/` with `chess` 1.11.2 + `pytest` 8.4.2
- [x] Routing — UCI command dispatch table in `ance/uci/loop.py` (`uci`, `isready`, `go`, `quit` recognized; anything else silently ignored per D-11)
- [x] State read/write — `ance.board.position.Position` wraps a fresh `chess.Board()`; `legal_moves()` is the "read," the worker's move selection is the "write" (in-memory only, no persistence this phase)
- [x] Interactive element wired end-to-end — a `go` command on stdin reaches a worker thread and produces a real `bestmove <uci>` line on stdout
- [x] "Deployment" — no server/cloud target for a local UCI engine; the equivalent is the documented local run command `<repo>/.venv/bin/python -m ance`, which Plan 01-06's GUI checkpoint registers directly in Cute Chess/Arena

## Out of Scope (Deferred Within/Beyond This Phase)

- Fail-soft alpha-beta pruning, iterative deepening, quiescence search — Phase 2
- `info depth … score cp … nodes … nps … pv …` search output — Phase 2 (UCI-11)
- Transposition table, move ordering (MVV-LVA/killers/history), real `wtime/btime` clock budgeting — Phase 3
- NNUE evaluation and the offline training pipeline — Phases 4–5
- `setoption` handling, tapered (blended) evaluation — v2 (CFG-01, EVAL-04)
- Mate-score ply-adjustment in the transposition table — no TT exists yet; deferred with the TT itself to Phase 2/3
- Console-script (`ance`) packaging entry point — `python -m ance` only, this milestone

## Subsequent Slice Plan (within Phase 1)

Each later plan in this phase thickens the skeleton without altering the
architectural decisions above:

- **Plan 01-02:** Real `position`/`ucinewgame` handling over the `Position`
  adapter, malformed-FEN/illegal-move rejection (D-10), terminal detection
  (SRCH-01), debug logging channel (D-18).
- **Plan 01-03:** The real fixed-depth negamax substrate behind the
  `Evaluator` seam (`ance/search/negamax.py`), full `go depth`/`movetime`/
  bare-`go`/`infinite` handling, `stop`/`quit` interrupt correctness,
  tie-break RNG (D-04), `bestmove (none)` for zero-legal-move positions
  (D-12).
- **Plan 01-04:** The full handcrafted evaluator — Simplified Evaluation
  Function piece values + PSTs + king mg/eg tables (D-05), plus mobility/
  bishop-pair/tempo/pawn-structure terms (D-06) — replacing the bootstrap
  `MaterialEval` as the engine's real eval (EVAL-02).
- **Plan 01-05:** The random-mover self-play gauntlet proving 100/100
  (TOOL-02).
- **Plan 01-06:** Manual GUI validation checkpoint in Cute Chess/Arena
  (TOOL-01).

Beyond this phase, per `.planning/ROADMAP.md`: Phase 2 adds alpha-beta +
iterative deepening + quiescence on top of this same negamax/eval seam;
Phase 3 adds the transposition table, move ordering, and real time
management; Phase 4 trains an NNUE offline; Phase 5 swaps the NNUE in
behind the same `Evaluator` seam established here.
