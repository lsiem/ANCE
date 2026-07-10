# Phase 3: Search Acceleration & Time Management - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 12 new/modified files
**Analogs found:** 11 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ance/search/transposition.py` (NEW) | service (search state) | CRUD (probe/store/clear) | `ance/search/types.py` | role-match (module conventions); no TT-like storage exists |
| `ance/search/ordering.py` (NEW) | utility (move scorer) | transform | `ance/search/negamax.py` `_mvv_lva_sort`/`_capture_value` (lines 89-113) | exact |
| `ance/search/negamax.py` (MOD) | service (search core) | request-response | itself — probe/store hooks slot into existing node structure | exact |
| `ance/search/types.py` (MOD) | model (context/result) | — | itself — extend `SearchContext` shared-reference fields | exact |
| `ance/uci/loop.py` (MOD) | controller (UCI dispatch) | event-driven | itself — `handle_go` deadline chain, `handle_ucinewgame` | exact |
| `ance/tools/gauntlet.py` (NEW) | tool/harness | batch (game loop) | `ance/tools/depth_vs_depth_match.py` | exact |
| `ance/tools/openings.epd` (NEW) | config (data file) | file-I/O | `OPENING_LINES` in `depth_vs_depth_match.py` lines 42-51 | role-match |
| `tests/test_transposition_table.py` (NEW) | test | — | `tests/test_tactical_search.py` | exact |
| `tests/test_move_ordering.py` (NEW) | test | — | `tests/test_tactical_search.py` | exact |
| `tests/test_time_management.py` (NEW) | test | — | `tests/test_search_deadline.py` | exact |
| `tests/test_gauntlet_harness.py` (NEW) | test | — | `tests/test_depth_vs_depth.py` | exact |
| `tests/test_phase3_strength_baseline.py` (NEW) | test/benchmark | — | `tests/test_phase2_strength_evidence.py` + node-counter pattern in `negamax.py` | role-match |

## Pattern Assignments

### `ance/search/transposition.py` (NEW module)

**Analog:** `ance/search/types.py` + `ance/search/negamax.py` module conventions. No existing storage analog — RESEARCH.md Pattern 1 supplies the implementation shape (fixed 2^20 tuple-slot list, index = `key & mask`, full-key verify, depth-preferred replace).

**Module header / imports pattern** (`ance/search/negamax.py` lines 1-27):
```python
"""Fail-soft alpha-beta negamax with quiescence, iterative deepening, and draw cuts.

This module imports only the `Evaluator` Protocol from `ance.eval.base` --
never any concrete evaluator class.
"""

from __future__ import annotations

import chess
import chess.polyglot

from ance.search.types import MATE_THRESHOLD, MAX_PLY, SearchContext
```
Convention: docstring names the design decision IDs; `from __future__ import annotations`; module-level UPPER_SNAKE constants (`NODE_POLL_INTERVAL = 2048` at line 26 is the style for `EXACT, LOWER, UPPER = 0, 1, 2`).

**Mate-threshold classifier already exists** (`ance/search/types.py` lines 13-16) — reuse, do not redefine:
```python
DEFAULT_BARE_GO_MOVETIME_MS = 2000
MAX_PLY = 64
# Mate-window classifier shared by wire formatter and eval-seam clamp (D-18).
MATE_THRESHOLD = MATE - MAX_PLY
```
Ply adjustment (D-04) uses this: store `score + ply` when `score > MATE_THRESHOLD`, `score - ply` when `< -MATE_THRESHOLD`; invert on probe (RESEARCH.md Pattern 1, verified against leaf convention below).

---

### `ance/search/ordering.py` (NEW module)

**Analog:** `ance/search/negamax.py` lines 30-113 — the MVV-LVA machinery to reuse (import or relocate), not duplicate.

**Piece values + capture value** (lines 30-37, 89-95):
```python
_MVV_LVA = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 10000,
}

def _capture_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return _MVV_LVA[chess.PAWN]
    if move.promotion is not None:
        return _MVV_LVA[move.promotion]
    piece = board.piece_at(move.to_square)
    return _MVV_LVA[piece.piece_type] if piece is not None else 0
```

**Sort-by-key pattern** (lines 98-105) — the new unified scorer follows this single-sort shape with the D-07 score bands (hash 1_000_000 > captures 100_000+ > killer0 90_000 > killer1 80_000 > history):
```python
def _mvv_lva_sort(moves: list[chess.Move], board: chess.Board) -> list[chess.Move]:
    def key(move: chess.Move) -> tuple[int, int]:
        victim = _capture_value(board, move)
        attacker_piece = board.piece_at(move.from_square)
        attacker = _MVV_LVA[attacker_piece.piece_type] if attacker_piece else 0
        return (victim, -attacker)

    return sorted(moves, key=key, reverse=True)
```
Constraint: `_qsearch_moves`/`quiescence_search` (lines 108-197) keep MVV-LVA only — do NOT thread the new scorer, TT, or killers into qsearch (D-07).

---

### `ance/search/negamax.py` (MOD — probe/store, ordering hooks, soft-limit gate)

**Core node pattern to modify** (lines 200-248). The existing structure the TT integrates into:
```python
def negamax(pos, depth, alpha, beta, ctx) -> int:
    ctx.counter[0] += 1
    _poll_stop(ctx)

    board = pos.board
    if _is_draw_position(pos, ctx):        # draw check FIRST — TT probe goes AFTER this
        return 0
    if depth == 0:
        return quiescence_search(pos, alpha, beta, ctx)

    ctx.path_keys.append(chess.polyglot.zobrist_hash(board))
    try:
        moves = pos.legal_moves()
        if not moves:
            return -(MATE - ctx.ply) if pos.is_check() else 0   # root-relative leaf mate
        best = -MATE - 1
        child_ply = ctx.ply + 1
        for move in moves:
            board.push(move)
            try:
                score = -negamax(pos, depth - 1, -beta, -alpha, _child_ctx(ctx, child_ply))
            finally:
                board.pop()
            if score > best:
                best = score
            if score >= beta:
                return score               # MUST become `break` so tt.store runs on exit
            if score > alpha:
                alpha = score
        return best
    finally:
        ctx.path_keys.pop()
```
Key facts for the planner:
- Leaf mate convention line 223: `-(MATE - ctx.ply)` — root-relative; TT stores node-relative (Pitfall 1).
- **Double zobrist compute exists** (`_is_draw_position` line 79 + `path_keys.append` line 218) — compute once at node entry, pass into both, plus probe/store (Pitfall 6).
- The `return score` fail-high (line 243) must become `break` so the store executes; behavior-identical score.

**Draw check to refactor for a passed key** (lines 77-86):
```python
def _is_draw_position(pos: Position, ctx: SearchContext) -> bool:
    board = pos.board
    key = chess.polyglot.zobrist_hash(board)
    if key in ctx.path_keys or key in ctx.game_history_keys:
        return True
    if board.is_fifty_moves():
        return True
    if board.is_insufficient_material():
        return True
    return False
```

**Context-clone propagation pattern** (lines 53-64) — new `tt`/`killers`/`history` fields MUST be added here or they silently reset per child (Pitfall 5):
```python
def _child_ctx(ctx: SearchContext, ply: int) -> SearchContext:
    return SearchContext(
        stop_flag=ctx.stop_flag,
        counter=ctx.counter,
        evaluator=ctx.evaluator,
        ply=ply,
        path_keys=ctx.path_keys,
        game_history_keys=ctx.game_history_keys,
        deadline=ctx.deadline,
        max_depth=ctx.max_depth,
        info_callback=ctx.info_callback,
    )
```
Also `_search_at_depth` (lines 276-285) constructs a **fresh SearchContext per root move** with `counter` shared but everything else defaulting — tt/killers/history must be passed in from one per-search object, not default-constructed there.

**Hard-stop poll pattern** (lines 44-50) — the granularity fix (2048 → ~512) lives here:
```python
NODE_POLL_INTERVAL = 2048   # line 26 — lower to ~512 for clock safety (Pitfall 3)

def _poll_stop(ctx: SearchContext) -> None:
    if ctx.counter[0] % NODE_POLL_INTERVAL != 0:
        return
    if ctx.stop_flag.is_set() or (
        ctx.deadline is not None and time.monotonic() >= ctx.deadline
    ):
        raise SearchAborted()
```

**Iterative-deepening loop for the soft-limit gate** (lines 331-355) — `start_time` already exists (line 328); the gate is one added check before `_search_at_depth`:
```python
    start_time = time.monotonic()
    target_depth = min(max_depth, MAX_PLY)

    for depth in range(1, target_depth + 1):
        if stop_flag.is_set():
            break
        if deadline is not None and time.monotonic() >= deadline:
            break
        # NEW: if soft_budget is not None and elapsed >= 0.5 * soft_budget and last_completed: break
        try:
            result = _search_at_depth(pos, depth, evaluator, stop_flag,
                                      game_history_keys, deadline, prior_best)
        except SearchAborted:
            break
```
`search_root` signature (lines 311-319) already uses keyword-only `deadline`/`info_callback` — add `soft_budget: float | None = None` in the same keyword-only style. Store-on-abort: `SearchAborted` raised inside the move loop naturally skips a store placed after the loop (Open Question 3 resolution).

---

### `ance/search/types.py` (MOD — SearchContext fields)

**Analog:** itself (lines 19-29). Shared-mutable-reference fields already exist — new fields follow the same shape:
```python
@dataclass
class SearchContext:
    stop_flag: threading.Event
    counter: list[int]                       # shared mutable ref — model for tt/killers/history
    evaluator: Evaluator
    ply: int = 0
    path_keys: list[int] = field(default_factory=list)
    game_history_keys: set[int] = field(default_factory=set)
    deadline: float | None = None
    max_depth: int = 0
    info_callback: Callable[..., None] | None = None
```
Add e.g. `tt: TranspositionTable | None = None`, `killers: list[list[chess.Move | None]] | None = None`, `history: list[list[list[int]]] | None = None` — defaulting to `None` keeps every existing constructor call site compiling; import via `from __future__ import annotations` (already present, line 3) avoids a circular import if the TT type is only annotated.

---

### `ance/uci/loop.py` (MOD — clock budget branch, ucinewgame clear)

**`handle_go` deadline-precedence chain to extend** (lines 182-221). D-13 precedence is exactly this if/elif chain — the clock branch is one new `elif`:
```python
def handle_go(cmd: GoCommand, pos: Position) -> None:
    global active_job, search_generation
    with generation_lock:
        search_generation += 1
        my_generation = search_generation
    _stop_active_worker()

    stop_event = threading.Event()
    job = SearchJob(generation=my_generation, stop_event=stop_event)
    depth = cmd.depth if cmd.depth is not None else MAX_PLY
    deadline: float | None = None
    if cmd.infinite:
        deadline = None
    elif cmd.depth is None and cmd.movetime is None:
        # <-- clock branch inserts here: when wtime/btime present, compute
        #     (soft_ms, hard_ms), set deadline from hard_ms; else bare-go default
        deadline = time.monotonic() + DEFAULT_BARE_GO_MOVETIME_MS / 1000
    elif cmd.movetime is not None:
        depth = MAX_PLY

    if cmd.movetime is not None:
        job.timer = threading.Timer(cmd.movetime / 1000, stop_event.set)
        job.timer.daemon = True
        job.timer.start()

    job.thread = threading.Thread(
        target=_run_search,
        args=(pos.copy(), depth, evaluator, stop_event, job.timer, my_generation, deadline),
        daemon=True,
    )
    active_job = job
    job.thread.start()
```
`_run_search` (lines 120-143) forwards `deadline` into `search_root` — thread `soft_budget` through the same args tuple. Clock fields available on `GoCommand` (`ance/uci/parser.py` lines 58-67: `wtime/btime/winc/binc: int | None`). Side to move: `pos.board.turn == chess.WHITE`. Note `handle_go` copies the position (`pos.copy()`) — read `turn` before or from the copy consistently.

**`handle_ucinewgame` — comment explicitly anticipates this phase** (lines 262-267):
```python
def handle_ucinewgame(pos: Position) -> None:
    # No-op reset of per-game state in M1 (D-17) -- no TT/history exists
    # yet. Stop/join with the same joined-flush / timed-out-invalidation
    # contract as handle_position, then reset the board.
    _stop_active_worker(invalidate_on_timeout=True)
    pos.try_set_startpos()
```
Add `tt.clear()` + killers/history reset after `_stop_active_worker(...)`. Per-process TT lives module-level next to `evaluator: Evaluator = HandcraftedEval()` (line 70) — that is the established engine-process-state pattern.

---

### `ance/tools/gauntlet.py` (NEW — TOOL-03 harness)

**Analog:** `ance/tools/depth_vs_depth_match.py` (game loop, color parity, aggregate dict, resume/callback API) + `ance/tools/phase2_deterministic_evidence.py` (subprocess launching).

**Game-loop + outcome classification pattern** (`depth_vs_depth_match.py` lines 84-116):
```python
    pos = Position()
    _apply_opening(pos, _opening_for_seed(seed))
    halfmoves = 0
    deep_color = chess.WHITE if deep_plays_white else chess.BLACK
    while not pos.board.is_game_over() and halfmoves < max_halfmoves:
        check_harness_expiry(event, deadline)
        ...
        pos.board.push(move)
        halfmoves += 1

    result = pos.board.result()
    if result == "1/2-1/2":
        return "draw"
    deep_won = (deep_color == chess.WHITE and result == "1-0") or (
        deep_color == chess.BLACK and result == "0-1"
    )
    return "win" if deep_won else "loss"
```
Phase 3 difference: engines are subprocesses driven via `chess.engine.SimpleEngine`, and the arbiter decrements wall-clocks itself (`chess.engine` does NOT adjudicate forfeits — RESEARCH.md Pattern 4 loop is the reference); use `claim_draw=True` per RESEARCH "Don't Hand-Roll".

**Color-parity + per-game aggregate pattern** (lines 154-197):
```python
    for game_index in range(start_game, n_games):
        check_harness_expiry(stop_event, deadline)
        deep_white = game_index % 2 == 0          # parity: color flips per game
        game_seed = seed + game_index             # opening derived from index
        outcome = play_depth_match_game(...)
        ...
        record = {"index": game_index, "seed": game_seed, "outcome": outcome}
        records.append(record)
        if on_game_complete is not None:
            on_game_complete(game_index, record, {...aggregate...})

    score_rate = (wins + 0.5 * draws) / n_games
    return {"wins": wins, "losses": losses, "draws": draws,
            "score_rate": score_rate, "n_games": n_games}
```
D-16 mapping: opening `i // 2`, color `i % 2` (each opening once per color). Extend the report dict with `time_forfeits` (D-14) and Wilson CI bounds (D-19; formula in RESEARCH Code Examples).

**Shared expiry helper — reuse, don't rewrite** (`ance/tools/random_mover_gauntlet.py` lines 63-75):
```python
def check_harness_expiry(stop_event, deadline) -> None:
    if stop_event is not None and stop_event.is_set():
        raise HarnessTimeout("cancelled: shared stop event is set")
    if deadline is not None and time.monotonic() >= deadline:
        raise HarnessTimeout(f"deadline expired (deadline={deadline})")
```

**Subprocess argv pattern** (`phase2_deterministic_evidence.py` lines 699-725) — argv lists, never `shell=True`:
```python
    child_argv = [sys.executable, "-m", "ance.tools.phase2_deterministic_evidence", "--output", ...]
    child = subprocess.Popen(child_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
```
For the arbiter: `chess.engine.SimpleEngine.popen_uci([sys.executable, "-m", "ance"])` per side; `shutil.which("cutechess-cli")` gates the passthrough runner; always `try/finally engine.quit()`.

---

### `ance/tools/openings.epd` (NEW)

**Analog (role only):** `OPENING_LINES` tuple in `depth_vs_depth_match.py` lines 42-51 (fixed, checked-in, balanced early openings, deterministic index selection). Phase 3 upgrades to an EPD file (~25-50 FEN lines) loaded with `chess.Board(fen)` — no PGN parsing (RESEARCH "Don't Hand-Roll").

---

### Test files (all NEW)

**Analog:** `tests/test_tactical_search.py` — the house test style:
```python
"""Tactical and mate-in-N search tests (D-13)."""

from __future__ import annotations

import threading

import chess

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.material import MaterialEval
from ance.search.negamax import search_root


def _never_stop() -> threading.Event:
    return threading.Event()


def test_mate_in_one_finds_mating_move() -> None:
    pos = Position(chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1"))
    result = search_root(pos, max_depth=2, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("a1a8")
    assert result.score >= MATE - 2
```
Conventions: module docstring citing decision IDs; plain functions (no classes); `_never_stop()` helper; FEN-literal positions; `MaterialEval` for deterministic cheap tests; typed `-> None`. Mate FENs here are reusable for D-22 (`test_mate_in_two_at_depth_four` FEN `6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1`).

Additional test analogs:
- `tests/test_search_deadline.py` → time-management tests (deadline/abort behavior; RESEARCH notes tools patch `time.monotonic` via module re-export — see `depth_vs_depth_match.py` line 18 `import time  # noqa: F401 (tests patch depth_match.time.monotonic)`).
- `tests/test_depth_vs_depth.py` → gauntlet-harness tests (parity, aggregate math, resume records).
- Slow marker registered in `pyproject.toml` line 10: `"slow: 100-game self-play gauntlet (deselect with -m 'not slow')"` — mark gauntlet/benchmark runs `@pytest.mark.slow`, keep a small smoke variant fast.
- Node-count benchmarks (D-20/D-21): `SearchResult.nodes` (cumulative across iterations, `negamax.py` lines 348-349) is the deterministic metric; measure TT-cold (Pitfall 9).

## Shared Patterns

### Generation-gated worker lifecycle
**Source:** `ance/uci/loop.py` lines 55-98, 161-169
**Apply to:** any `handle_go`/`handle_ucinewgame` changes — never bypass `_stop_active_worker()` / `generation_lock`; clock stop must reuse the existing `stop_event`/`deadline`/`Timer` plumbing, not add a second mechanism.

### Zobrist keying
**Source:** `ance/search/negamax.py` lines 67-86 (`_build_game_history_keys`, `_is_draw_position`)
**Apply to:** TT keys — `chess.polyglot.zobrist_hash(board)` (D-05), computed once per node and shared with draw check / path push / probe / store.

### Root-relative mate scoring
**Source:** `negamax.py` line 223 / `quiescence_search` line 141: `-(MATE - ctx.ply)`; classifier `MATE_THRESHOLD = MATE - MAX_PLY` (`types.py` line 16)
**Apply to:** TT store/probe ply adjustment (D-04) — conversion lives only at the TT module boundary.

### push/try/finally/pop board discipline
**Source:** `negamax.py` lines 229-239 (and 274-291 root variant)
**Apply to:** any new move-loop code:
```python
board.push(move)
try:
    score = -negamax(...)
finally:
    board.pop()
```

### Bounded evidence / slow-marked tooling
**Source:** `ance/tools/phase2_deterministic_evidence.py` (supervisor deadline, `remaining_time`, watchdog, atomic checkpoints) + `check_harness_expiry` in `random_mover_gauntlet.py`
**Apply to:** gauntlet runs and baseline evidence — hard wall-clock bounds, resume records, exact command lines recorded for SUMMARY (D-19).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `ance/search/transposition.py` (storage internals) | service | CRUD | No fixed-size keyed cache exists anywhere in the codebase; use RESEARCH.md Pattern 1 recommended class verbatim as the starting shape (module conventions still copied from `negamax.py`/`types.py`) |

## Metadata

**Analog search scope:** `ance/search/`, `ance/uci/`, `ance/tools/`, `tests/`, `pyproject.toml`
**Files scanned:** 8 read in depth (negamax.py, types.py, loop.py, parser.py, depth_vs_depth_match.py, random_mover_gauntlet.py excerpt, phase2_deterministic_evidence.py excerpt, test_tactical_search.py) of 24 candidates
**Pattern extraction date:** 2026-07-11
