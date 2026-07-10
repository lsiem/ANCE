# Phase 3: Search Acceleration & Time Management - Research

**Researched:** 2026-07-10
**Domain:** Classical chess-engine search infrastructure (transposition table, move ordering, clock management) + engine-vs-engine gauntlet tooling, all in pure Python on python-chess
**Confidence:** HIGH (algorithms are decades-standard; codebase integration points verified by reading source; tooling availability verified against registries/release assets)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Locked upstream (carried forward — do NOT re-open)
- **D-00a–D-00c:** Eval seam, reader/worker threading, `python-chess` board adapter, hand-written UCI loop. *(Phases 1–2)*
- **D-02–D-08, D-18–D-19:** Qsearch design, draw/terminal contracts, info output, mate wire format. *(Phase 2)*
- **D-10:** Deterministic tie-break (first legal / prior-iteration root move). *(Phase 2)*

#### Transposition table (SRCH-05)
- **D-01:** **Fixed-size TT** starting at **2^20 entries (~1M)**; entry = `{key, depth, score, flag, best_move}`; pure-Python list/dict or compact array — planner chooses, size is the locked budget.
- **D-02:** **Depth-preferred replacement**: replace when empty or incoming depth ≥ stored depth; never shallow-over-deep.
- **D-03:** **Bound flags** EXACT / LOWER / UPPER with fail-soft alpha-beta semantics; probe cutoffs only when depth and bounds allow.
- **D-04:** **Mate scores** stored and retrieved with **ply adjustment** (same convention as negamax leaf mate scoring).
- **D-05:** **Zobrist key** = `chess.polyglot.zobrist_hash(board)` (consistent with Phase 2 path/history keys).
- **D-06:** **`ucinewgame` clears the entire TT** — no cross-game leakage (ROADMAP success criterion 4).

#### Move ordering (SRCH-06)
- **D-07:** Main-search order: **TT hash move → MVV-LVA captures → killers → history heuristic → remaining quiet moves**. Qsearch keeps **MVV-LVA only** (Phase 2 D-04 unchanged).
- **D-08:** **Two killer slots per ply**; cleared on `ucinewgame`.
- **D-09:** **History heuristic** (from/to or move-index table); age or clear on `ucinewgame` — planner picks representation; table must not grow without bound across a game.
- **D-10:** TT best move feeds hash-move slot; killers updated on beta cutoffs at non-PV nodes (standard heuristic — exact cutoff policy is planner discretion).

#### Clock management (SRCH-08 / UCI-08)
- **D-11:** **`GoCommand` already parses clock fields** (`ance/uci/parser.py`); Phase 3 **acts on** `wtime`/`btime`/`winc`/`binc` when present and `movetime` is absent.
- **D-12:** **Soft budget** = function of remaining side time + increment credit (simple divide-by-estimated-moves-left or urgency curve — planner chooses formula); **hard stop** with **≥150ms safety margin** before flag fall.
- **D-13:** Precedence unchanged: explicit **`movetime`** or **`depth`** or **`infinite`** overrides clock budgeting (Phase 2 behavior preserved).
- **D-14:** **Never lose on time** is a hard acceptance gate: **100-game blitz gauntlet** with clock fields must report **zero time forfeits**.

#### Gauntlet harness (TOOL-03)
- **D-15:** **Primary runner: `cutechess-cli`** when available on PATH (e.g. `brew install cutechess`); **fallback: python-chess external arbiter** with the same opening book and UCI clock args — macOS has no Cute Chess GUI binary, but CLI may still be installable; fallback must not block Phase 3 completion.
- **D-16:** **Fixed opening book** (PGN or EPD subset) shared across both sides; deterministic seed / game-index parity for color (reuse Phase 2 depth-match patterns where applicable).
- **D-17:** **Sanity gauntlet:** handcrafted vs handcrafted, **~100 games**, score ≈ **50% ± noise** (validates harness, not eval strength).
- **D-18:** Harness API must support **two engine commands/builds differing only in eval** later (Phase 5); Phase 3 proves the plumbing with identical eval.
- **D-19:** Report **W-L-D + draw rate + optional Wilson 95% CI** on score percentage; record exact CLI/arbiter command lines in SUMMARY.

#### Strength proof vs Phase 2 baseline
- **D-20:** **Snapshot Phase 2 baseline** before TT/ordering land: completed depth and nodes at **2s movetime** on a fixed FEN set (store artifact or test constants).
- **D-21:** Phase 3 must show **measurably greater completed depth or fewer nodes to same depth** at equal 2s budget vs baseline (pytest benchmark, not hand-waved).
- **D-22:** **Mate-in-2/3 positions** report stable **`score mate N`** across increasing depths once TT is warm (ROADMAP criterion 1).
- **D-23:** Re-run **fast pytest suite** (`-m "not slow"`) after each plan; no regression in Phase 2 draw/qsearch/UCI contracts.

### Claude's Discretion
- Exact TT entry layout and probe/store cutover conditions.
- History table dimensions and aging policy.
- Clock urgency formula details inside D-12 margin.
- Whether cutechess or arbiter is default on CI vs dev machine.

### Deferred Ideas (OUT OF SCOPE)
- **Aspiration windows / LMR / null-move pruning** — strength beyond ordering+TT; future milestone.
- **Statistical Elo / 1000+ game gauntlet (TOOL-04)** — Phase 5 after NNUE swap.
- **Collector artifact source-identity hash** — evidence harness hardening; optional tooling plan.
- **nodes limit / searchmoves / ponder** — UCI params parsed or skipped only.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRCH-05 | Zobrist-keyed transposition table with correct exact/lower/upper bounds and ply-adjusted mate scores on store and probe | "TT Pattern" + "Mate-score ply adjustment" sections: full store/probe algorithm matched to ANCE's fail-soft negamax and `-(MATE - ply)` leaf convention; fixed-size list-indexed table design under D-01 |
| SRCH-06 | Move ordering hash-move → MVV-LVA captures → killers → history | "Move-ordering Pattern": single scoring-function sort integrating existing `_mvv_lva_sort`, two killer slots per ply, butterfly history table; measurement via nodes-to-fixed-depth and first-move-cutoff rate |
| SRCH-08 | Clock management so engine never loses on time under `wtime/btime/winc/binc` | "Time-management Pattern": soft/hard budget formulas for 10–50k nps pure Python, poll-granularity fix (NODE_POLL_INTERVAL), 150ms+ margin analysis, soft-limit iteration gating with high EBF |
| UCI-08 | Engine honors clock control and computes a per-move budget | "Clock wiring" in Architecture Patterns: `handle_go` budget branch (precedence per D-13), reuse of existing `deadline` + `stop_event` plumbing verified in `ance/uci/loop.py` |
| TOOL-03 | cutechess-cli self-play gauntlet harness, two builds, fixed opening book | "Gauntlet harness Pattern" + Environment Availability: cutechess-cli has NO macOS binary (verified) → python-chess arbiter is default runner on this machine, with cutechess-cli/fastchess command generation when available; arbiter must self-referee clocks (verified: `chess.engine` does not adjudicate forfeits) |
</phase_requirements>

## Summary

Phase 3 adds the three classical search accelerators (transposition table, full move ordering, real time management) plus a self-play gauntlet harness. **Nothing here needs a new dependency** — every algorithm is implementable on the already-installed `chess` 1.11.2 + stdlib, and every algorithm is 30+-years-standard with authoritative documentation on the Chess Programming Wiki. The hard parts are not the algorithms but (a) the *integration* with ANCE's existing fail-soft negamax, root-relative mate scoring, per-node `SearchContext` cloning, and generation-gated UCI worker; and (b) the *pure-Python performance reality* — at 10–50k nps, defaults tuned for compiled engines (poll intervals, blitz time controls, gauntlet runtimes) are wrong by 2–3 orders of magnitude and must be recalibrated.

Two environment facts change the plan shape versus what CONTEXT.md assumed. First, **cutechess-cli is effectively unavailable on this machine**: there is no `cutechess` Homebrew formula (verified: `brew info` error) and the v1.5.1 release (2026-06-14) ships only Windows and Linux assets — building locally needs a Qt 6.8 toolchain. D-15's fallback (python-chess arbiter) is therefore the *default* runner, not the backup; the harness should still emit/accept a cutechess-style invocation for machines that have it, and `fastchess` (verified `fastchess-mac-arm64.tar` release asset) is a drop-in cutechess-compatible alternative if a native runner is wanted. Second, **`chess.engine` does not referee clocks** (verified in installed source: `Limit(white_clock=…)` is merely translated to `go wtime …`), so the arbiter must decrement clocks from wall time and adjudicate flag falls itself — that is exactly what makes D-14's "zero time forfeits" gate measurable.

**Primary recommendation:** Build in four plan-sized chunks in this order — (1) TT module + negamax probe/store + mate-ply adjustment + `ucinewgame` clear, (2) move-ordering scorer (hash move / MVV-LVA / killers / history) threaded through `SearchContext`, (3) clock budgeting in `handle_go` + soft-limit iteration gating in `search_root` + poll-interval fix, (4) gauntlet harness (python-chess arbiter default, cutechess-cli passthrough) + baseline/strength evidence — snapshotting the Phase 2 baseline (D-20) **before** chunk 1 lands.

## Project Constraints (from CLAUDE.md)

- **Pure Python 3.12+ (venv is python3.13 arm64), `python-chess` for board/movegen** — no compiled hot-path port this milestone; code stays modular for a future port.
- **`chess.engine` is for *driving* external engines only** (gauntlets, labeling) — ANCE's own UCI loop stays hand-written. The Phase 3 arbiter driving two ANCE processes via `chess.engine.SimpleEngine` is the sanctioned use.
- **Evaluation must stay a swappable module** — TT/ordering/clock code must not import concrete evaluators; `negamax.py` imports only the `Evaluator` Protocol (existing pattern, keep it).
- **Search-strength additions beyond TT+ordering are out of scope** (LMR, null-move, aspiration — v2 requirements SRCH-09..11).
- **TDD RED/GREEN atomic commits per plan task** (established Phase 1–2 pattern; ECC rules mandate tests-first, pytest, AAA structure).
- **GSD workflow enforcement** — implementation happens via `/gsd-execute-phase`, not ad-hoc edits.
- **No new heavy dependencies** — the stack table in CLAUDE.md is the committed stack; Phase 3 needs nothing beyond it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TT storage/probe/replacement | Search core (`ance/search/`) | — | Pure search-state concern; must be reachable from every negamax node via `SearchContext` |
| TT lifetime & `ucinewgame` clear | UCI layer (`ance/uci/loop.py`) | Search core | TT persists *across* `go` commands within a game → owned by engine process state in `loop.py`, cleared by `handle_ucinewgame` (D-06) |
| Move ordering (hash/MVV-LVA/killers/history) | Search core | — | Ordering tables live/die with search+game state; qsearch ordering (MVV-LVA) already exists and is untouched (D-07) |
| Per-move time budget computation | UCI layer (`handle_go`) | — | Budget derives from the `go` command's clock fields + side to move; search only receives soft budget + hard deadline |
| Soft-limit iteration gating & hard-stop enforcement | Search core (`search_root` / `_poll_stop`) | — | Only the search loop knows iteration boundaries and node cadence |
| Gauntlet harness & clock refereeing | Tools tier (`ance/tools/`) | External process (cutechess-cli/fastchess) | Arbiter is a *client* of two engine subprocesses; never linked into engine code |
| Baseline/strength evidence | Tests + Tools tier | — | pytest benchmarks (deterministic node counts) + slow-marked gauntlet tools, mirroring `phase2_deterministic_evidence.py` |

## Standard Stack

### Core (all already installed — zero new packages)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `chess` (python-chess) | 1.11.2 (verified in venv) | Board, movegen, `chess.polyglot.zobrist_hash`, `chess.engine` for the arbiter, `chess.pgn` for game records | Already the project board layer; `zobrist_hash` already keys the Phase 2 draw paths (D-05) [VERIFIED: installed venv] |
| Python stdlib `threading`, `time` | 3.13 | Deadline (`time.monotonic`), stop events, timers | Existing Phase 2 plumbing in `loop.py`/`negamax.py` [VERIFIED: codebase] |
| `pytest` | installed (markers configured, `slow` marker exists) | RED/GREEN tests, deterministic benchmarks | Existing suite of 17 test modules; `-m "not slow"` fast lane already used by D-23 [VERIFIED: pyproject.toml] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `chess.engine.SimpleEngine` | bundled with chess 1.11.2 | Drive two `python -m ance` subprocesses in the arbiter | Gauntlet fallback runner (default on this machine — see Environment Availability) |
| `math` (stdlib) | — | Wilson 95% CI computation (D-19) | Gauntlet report |

### External tools (optional, NOT pip packages)

| Tool | Status on this machine | Purpose |
|------|------------------------|---------|
| `cutechess-cli` 1.5.1 | **Unavailable** — no macOS release asset, no brew formula [VERIFIED: gh api release assets + brew] | Primary runner per D-15 *when present on PATH* |
| `fastchess` v1.8.0-alpha | Not installed; prebuilt `fastchess-mac-arm64.tar` exists on GitHub releases [VERIFIED: gh api release assets] | Optional native runner alternative (cutechess-compatible CLI) — user-install decision, do not auto-download |
| Stockfish | Not installed (verified `which`) | **Not needed in Phase 3** (gauntlet is ANCE-vs-ANCE); needed Phase 4 |

**Installation:** none. Phase 3 installs zero Python packages.

## Package Legitimacy Audit

**This phase installs no external packages.** All Python dependencies (`chess` 1.11.2, `pytest`) are already installed and were audited in prior phases. External binaries (cutechess-cli, fastchess) are optional native tools obtained from their official GitHub release pages, not package registries, and the plan must not auto-install them — D-15's arbiter fallback removes the need.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                       GUI / gauntlet runner (stdin)
                                  │
                    ┌─────────────▼──────────────┐
                    │  UCI reader thread (loop.py)│
                    │  parse_go → clock fields    │
                    └─────┬───────────┬──────────┘
        ucinewgame ───────┤           │ go wtime/btime/winc/binc
   clear TT+killers+hist  │           ▼
                    ┌─────▼──────────────────────┐
                    │ handle_go: budget computer  │
                    │ soft_ms, hard deadline      │  (movetime/depth/infinite
                    │ (D-12/D-13 precedence)      │   bypass budgeting, D-13)
                    └─────────────┬──────────────┘
                                  │ spawn worker (existing generation gating)
                    ┌─────────────▼──────────────┐
                    │ search_root (negamax.py)    │
                    │ iterative deepening         │◄── soft limit: skip next
                    │                             │    iteration if elapsed
                    └─────┬───────────────────────┘    exceeds gate fraction
                          │ per depth
                    ┌─────▼──────────────────────┐
                    │ negamax node                │
                    │ 1. draw check (existing)    │
                    │ 2. key = zobrist (ONCE)     │
                    │ 3. TT probe → cutoff/hash mv│──── TranspositionTable
                    │ 4. order moves:             │     (fixed 2^20 slots,
                    │    hash→MVV-LVA→killer→hist │      depth-preferred)
                    │ 5. search children          │──── killers[ply][2]
                    │ 6. beta cutoff → killers/   │──── history[color][from][to]
                    │    history update           │
                    │ 7. TT store (flag+mate adj) │
                    │ 8. _poll_stop (hard stop)   │
                    └─────────────────────────────┘

   Gauntlet (separate tool tier, ance/tools/gauntlet.py):
   arbiter ──popen_uci──► ANCE build A (python -m ance)
     │      ──popen_uci──► ANCE build B (python -m ance)
     │  per move: t0=monotonic → engine.play(Limit(white_clock…)) →
     │  clock -= elapsed; clock<0 → TIME FORFEIT; clock += inc
     └─► W-L-D + draw rate + Wilson CI report
        (or: generate & exec cutechess-cli/fastchess command when on PATH)
```

### Recommended Project Structure (additions only)

```
ance/
├── search/
│   ├── negamax.py         # + TT probe/store, ordering hooks, soft-limit gate
│   ├── types.py           # + SearchContext fields: tt, killers, history, node_key?
│   ├── transposition.py   # NEW: TranspositionTable (fixed 2^20, flags, mate adj)
│   └── ordering.py        # NEW: move scorer (hash/MVV-LVA/killers/history)
├── uci/
│   └── loop.py            # + clock budget in handle_go; ucinewgame clears tables
└── tools/
    ├── gauntlet.py        # NEW: TOOL-03 harness (arbiter default + cutechess cmd gen)
    └── openings.py|.epd   # NEW: fixed opening set (EPD lines checked into repo)
tests/
    ├── test_transposition_table.py
    ├── test_move_ordering.py
    ├── test_time_management.py
    ├── test_gauntlet_harness.py
    └── test_phase3_strength_baseline.py   # D-20/D-21 evidence
```

### Pattern 1: Transposition table on ANCE's fail-soft negamax (SRCH-05)

**What:** Fixed-size, index-mapped table probed after the draw check and stored on node exit, with node-relative mate scores.

**Store flags with fail-soft semantics** (matches `negamax()`'s existing `best` tracking) [CITED: chessprogramming.org/Transposition_Table; mediocrechess.blogspot.com TT guide]:
- Record `alpha_orig = alpha` at node entry.
- On exit: `best >= beta` → **LOWER** (fail-high); `best <= alpha_orig` → **UPPER** (fail-low); else **EXACT**.
- Probe cutoff only when `entry.depth >= depth` AND (`EXACT`, or `LOWER and score >= beta`, or `UPPER and score <= alpha`). When depth is insufficient, still use `entry.best_move` for ordering.

**Fixed-size layout under D-01** (planner discretion on exact layout; this is the recommended shape):
```python
# ance/search/transposition.py — recommended shape
# Source: standard always-index scheme (CPW Transposition Table), adapted to pure Python
EXACT, LOWER, UPPER = 0, 1, 2

class TranspositionTable:
    def __init__(self, size_pow2: int = 1 << 20) -> None:
        self._mask = size_pow2 - 1
        self._entries: list[tuple[int, int, int, int, chess.Move | None] | None] = (
            [None] * size_pow2
        )  # (key, depth, score, flag, best_move)

    def probe(self, key: int) -> tuple[int, int, int, chess.Move | None] | None:
        entry = self._entries[key & self._mask]
        if entry is None or entry[0] != key:   # full-key verification vs index collision
            return None
        return entry[1:]

    def store(self, key: int, depth: int, score: int, flag: int,
              best_move: chess.Move | None) -> None:
        idx = key & self._mask
        old = self._entries[idx]
        if old is None or depth >= old[1]:     # depth-preferred (D-02)
            self._entries[idx] = (key, depth, score, flag, best_move)

    def clear(self) -> None:                   # ucinewgame (D-06)
        self._entries = [None] * (self._mask + 1)
```
Tuples over dataclasses: ~2–3× cheaper to allocate/read in CPython, and single-slot list assignment is atomic under the GIL (relevant to the bounded-join stale-worker window — see Pitfall 7). Memory: ~150–250 MB *if completely full*; at 10–50k nps a game fills only a small fraction — acceptable on 24 GB, but see Pitfall 8.

**Mate-score ply adjustment (D-04)** — the single most bug-prone line of the phase. ANCE's convention (verified in `negamax.py`): a mated side at node ply `p` (distance from root) returns `-(MATE - p)`, i.e. scores in the tree are **root-relative**. The same position reached at a different root distance must yield the same TT entry, so entries must be **node-relative** [ASSUMED — standard Bruce Moreland convention, derived below and empirically pinned by D-22's stable-`mate N` tests]:

```python
# On STORE at node ply `ply` (score is root-relative, |score| > MATE_THRESHOLD):
if score > MATE_THRESHOLD:   tt_score = score + ply    # MATE - dist_from_node
elif score < -MATE_THRESHOLD: tt_score = score - ply
else:                         tt_score = score

# On PROBE at node ply `ply` (convert back to root-relative):
if tt_score > MATE_THRESHOLD:   score = tt_score - ply
elif tt_score < -MATE_THRESHOLD: score = tt_score + ply
```
Derivation check: score `MATE - m` (mate at root-ply `m`) stored at node ply `p` becomes `MATE - (m - p)` = "mate `m-p` plies below this node" — position-intrinsic. Probing at ply `p'` yields `MATE - (m - p) - ... ` → `MATE - ((m-p) + p')`, i.e. mate at root-ply `p' + dist` — exactly right. `MATE_THRESHOLD = MATE - MAX_PLY` (existing, `types.py`) is the correct classifier on both sides because node-relative mate magnitudes are *larger* than root-relative ones.

**Probe placement:** after `_is_draw_position` (per CONTEXT integration note) — draw detection is path-dependent and must never be short-circuited by a TT hit. Compute `chess.polyglot.zobrist_hash(board)` **once** per node and reuse it for the draw check, `path_keys.append`, probe, and store — the current code already computes it twice per node; a third computation would be pure waste (see Pitfall 6).

**Root handling:** `_search_at_depth` iterates root moves explicitly and must return a move — never take a TT *cutoff* at the root. The TT's root contribution is (a) subtree cutoffs below root and (b) `best_move` ordering; the existing `prior_best` mechanism already orders the previous iteration's move first and stays as-is.

### Pattern 2: Unified move-ordering scorer (SRCH-06)

**What:** One scoring function over the legal move list, single `sort`, replacing per-category list surgery. Score bands guarantee the D-07 order:

```python
# ance/search/ordering.py — score bands (descending sort)
# Source: CPW Move Ordering / Killer Heuristic / History Heuristic
HASH_MOVE_SCORE   = 1_000_000
CAPTURE_BASE      =   100_000   # + victim*100 - attacker (reuses _capture_value / _MVV_LVA)
KILLER_0_SCORE    =    90_000
KILLER_1_SCORE    =    80_000
# quiet moves: history[color][from][to] (always < 80_000 after aging — see D-09 note)

def score_move(move, board, hash_move, killers_at_ply, history) -> int:
    if move == hash_move:
        return HASH_MOVE_SCORE
    if board.is_capture(move) or move.promotion is not None:
        return CAPTURE_BASE + 100 * _capture_value(board, move) - _attacker_value(board, move)
    if move == killers_at_ply[0]:
        return KILLER_0_SCORE
    if move == killers_at_ply[1]:
        return KILLER_1_SCORE
    return history[int(board.turn)][move.from_square][move.to_square]
```

**Killers (D-08):** `killers = [[None, None] for _ in range(MAX_PLY + 1)]`. On a **quiet** move causing a beta cutoff at ply `p`: if `move != killers[p][0]`, shift slot 0 → slot 1, store move in slot 0. Killers are moves-from-*other*-branches — they may be illegal in the current position, which is harmless here because scoring only ranks moves already in the legal list. Cleared on `ucinewgame`. [CITED: chessprogramming.org/Killer_Heuristic]

**History (D-09):** butterfly table `history[2][64][64]` (nested lists; ~8k ints). On quiet beta cutoff: `history[side][from][to] += depth * depth`. To satisfy D-09's no-unbounded-growth AND keep quiet scores below `KILLER_1_SCORE`: when any cell exceeds a cap (e.g. 79_000), halve the whole table (aging). Cleared on `ucinewgame`. [CITED: chessprogramming.org/History_Heuristic]

**Threading through `SearchContext`:** killers/history/tt must be *shared references* across `_child_ctx` clones — same pattern as the existing `counter`/`path_keys`/`game_history_keys` fields. Add `tt`, `killers`, `history` fields to `SearchContext` and propagate them in `_child_ctx`. They must ALSO be shared across the per-root-move `SearchContext` constructions in `_search_at_depth` (currently rebuilt per root move — the new fields must come from one per-search/per-game object, not fresh defaults, or the TT will silently reset every root move).

**Qsearch untouched:** D-07 locks qsearch to MVV-LVA only — do not probe TT or killers in `quiescence_search`.

**Measurement (success criterion 2):** two metrics, both already computable from existing plumbing: (a) **nodes-to-fixed-depth** on a fixed FEN set (deterministic, CI-safe — expect 2–5× reduction at depth 4–5 from ordering+TT combined [ASSUMED — typical range, exact factor is position-dependent]); (b) completed depth at equal 2s movetime vs the D-20 baseline (wall-clock, dev-machine evidence). Optionally instrument first-move-cutoff rate (fraction of beta cutoffs on the first searched move; >85–90% is the classic health signal [ASSUMED]).

### Pattern 3: Clock management (SRCH-08 / UCI-08)

**What:** `handle_go` computes `(soft_ms, hard_ms)` from clock fields; search enforces the soft limit *between* iterations and the hard limit *inside* nodes via the existing deadline/`_poll_stop` machinery. [CITED: chessprogramming.org/Time_Management — soft/optimum bound checked per ID iteration, hard/maximum bound checked every N nodes]

**Recommended formula** (planner discretion inside D-12; keep it boring):
```python
# handle_go, when wtime/btime present and movetime/depth/infinite absent (D-11/D-13)
remaining = cmd.wtime if pos.board.turn == chess.WHITE else cmd.btime
inc       = (cmd.winc if pos.board.turn == chess.WHITE else cmd.binc) or 0

SAFETY_MS = 200          # ≥150 per D-12; extra headroom for poll latency (see below)
MIN_BUDGET_MS = 20

soft_ms = remaining / 25 + inc * 0.6            # ~25 moves-to-go estimate + inc credit
hard_ms = min(soft_ms * 4, remaining / 3)       # never bet a third of the clock on one move
hard_ms = max(MIN_BUDGET_MS, min(hard_ms, remaining - SAFETY_MS))
soft_ms = min(soft_ms, hard_ms)
deadline = time.monotonic() + hard_ms / 1000
```
The exact divisors matter far less than the invariants: `hard ≤ remaining − safety`, `soft ≤ hard`, and a floor so depth 1 always completes (the existing `search_root` fallback returns the first legal move even if zero iterations finish, so a flag can never cause an illegal/missing bestmove — verified in `negamax.py`).

**Soft-limit iteration gating** — critical in pure Python. Each ID iteration costs roughly EBF× the previous one, and with ordering+TT the EBF will still be ~4–8 here [ASSUMED — pure-Python, no pruning beyond alpha-beta]. Starting an iteration that cannot finish burns the whole remaining budget for zero usable output (last-completed-depth is what's kept). Rule: in `search_root`, before starting depth d+1, stop if `elapsed >= gate * soft_budget` with `gate ≈ 0.4–0.6` (planner picks; 0.5 is a fine default). `search_root` needs the soft budget as a new parameter alongside the existing `deadline`.

**Hard-stop granularity (must fix):** `_poll_stop` checks only every `NODE_POLL_INTERVAL = 2048` nodes. At 10k nps that is ~200 ms between checks — *larger than the 150 ms safety margin*, so a flag fall is possible even with a correct deadline. Fix options (planner discretion): lower the interval to 256–512 (≈5–50 ms at 10–50k nps; the `%` check itself costs ~nothing relative to Python node cost), or make the safety margin ≥ worst-case poll latency + output latency. Recommend both: interval 512 and `SAFETY_MS = 200`.

**Reuse, don't rebuild:** the deadline plumbing (`deadline` param → `_poll_stop` → `SearchAborted`), the movetime `threading.Timer`, the stop event, and generation gating all exist and were verified in `loop.py`/`negamax.py`. The clock branch is one new `elif` in `handle_go`'s deadline computation plus the soft-budget parameter — the D-13 precedence order falls out of the existing `if cmd.infinite / elif bare / elif movetime` chain with one added clock case.

### Pattern 4: Gauntlet harness (TOOL-03)

**What:** `ance/tools/gauntlet.py` with a runner-agnostic core: takes two engine command lines, an opening set, a time control, and game count; returns per-game results + aggregate report (D-18's Phase 5 reuse contract).

**Runner selection (D-15, discretion resolved by environment facts):**
- `shutil.which("cutechess-cli")` → generate and `subprocess.run` a cutechess-cli invocation, parse its result line. On this machine it will not be found (verified — no macOS asset, no brew formula), but CI/other machines may have it, and TOOL-03 names it.
- Default on this machine: **python-chess arbiter**. `chess.engine.SimpleEngine.popen_uci([sys.executable, "-m", "ance"])` per side (entry point exists: `ance/__main__.py`; `sys.executable`-based subprocess launching is the established pattern in `phase2_deterministic_evidence.py`).
- Optional: accept a `fastchess` binary path — its CLI is cutechess-compatible for this use; a prebuilt `fastchess-mac-arm64.tar` exists (v1.8.0-alpha, 2026-01-28) if the user chooses to install it. Do not auto-download.

**Arbiter must referee clocks itself** — `chess.engine` will happily pass `Limit(white_clock=…, black_clock=…, white_inc=…, black_inc=…)` to the engine as `go wtime/btime/winc/binc` (verified in installed `chess/engine.py` lines 1545–1556) but performs **no forfeit adjudication**. The arbiter loop:

```python
# Source: verified chess.engine semantics (installed chess 1.11.2)
clocks = {chess.WHITE: tc_base_s, chess.BLACK: tc_base_s}
while not board.is_game_over(claim_draw=True):
    side = board.turn
    limit = chess.engine.Limit(
        white_clock=clocks[chess.WHITE], black_clock=clocks[chess.BLACK],
        white_inc=inc_s, black_inc=inc_s,
    )
    t0 = time.monotonic()
    result = engines[side].play(board, limit)
    elapsed = time.monotonic() - t0
    clocks[side] -= elapsed
    if clocks[side] < 0:
        record_time_forfeit(side)          # D-14: gauntlet must report zero of these
        break
    clocks[side] += inc_s
    board.push(result.move)
```
Wall-time measurement includes IPC/parse overhead (~1–5 ms/move) — that is what a real arbiter (or lichess) charges too; the engine's safety margin must absorb it. Count and report forfeits explicitly: **zero forfeits across the 100-game blitz gauntlet is the D-14 gate.**

**Openings & color parity (D-16):** a fixed EPD file (~25–50 balanced early-middlegame positions) checked into the repo; game `i` uses opening `i // 2`, colors determined by `i % 2` — each opening played once per color, mirroring `depth_vs_depth_match.py`'s parity pattern. EPD over PGN: one `chess.Board(fen)` call, no PGN parsing.

**Report (D-19):** W-L-D, score %, draw rate, Wilson 95% CI:
```python
import math
def wilson_ci(score_points: float, n: int, z: float = 1.96) -> tuple[float, float]:
    p = score_points / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half
```
Sanity check (D-17): identical builds over ~100 games → CI must contain 0.50. With n=100 the Wilson half-width is ~±10% — assert "CI contains 50%", not "score == 50%".

**Runtime budgeting (pure-Python reality):** at a blitz TC the per-move cost is the TC itself, not the search quality. 100 games × ~80 moves/game at e.g. 30s+0.3s each side ≈ up to ~2 min/game worst case → **2.5–4 hours for the full 100-game run**. Choose the smallest TC that still exercises clock logic (e.g. 30+0.3 or even 10+0.1 — the never-flag property is *harder* at faster TCs, which is what we want to prove); run it as a `slow`-marked tool/test with a small (4–10 game) fast smoke variant in the default suite.

### Anti-Patterns to Avoid

- **TT cutoff before the draw check** — repetition/50-move detection is path-dependent; probing first returns stale non-draw scores in repeated positions. Probe after `_is_draw_position` (CONTEXT already mandates this).
- **Storing root-relative mate scores in the TT** — produces oscillating/wrong `mate N` across depths, the exact failure D-22's test exists to catch.
- **Taking TT cutoffs at the root node** — can return a score with no move; root iterates moves explicitly.
- **Probing the TT in qsearch** — locked out by D-07; also of marginal value at ANCE's node rates.
- **A second hand-rolled UCI client for the arbiter** — `chess.engine` is the sanctioned client (CLAUDE.md); write only the clock-refereeing loop around it.
- **Trusting `chess.engine` to detect flag falls** — it does not; without arbiter-side clocks D-14 is unverifiable.
- **Time-based assertions in the fast test lane** — wall-clock benchmarks are machine/load-sensitive; deterministic node-count comparisons belong in CI, timed evidence in `slow`/tools (Phase 2's `phase2_deterministic_evidence.py` precedent).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Position hashing | Custom Zobrist tables + incremental updates | `chess.polyglot.zobrist_hash(board)` | Locked by D-05; consistent with Phase 2 draw keys; incremental hashing is a compiled-port optimization, and correctness bugs in custom Zobrist are notoriously silent |
| UCI client for the arbiter | stdin/stdout protocol driver | `chess.engine.SimpleEngine.popen_uci` | Handles handshake, isready sync, info parsing, crash cleanup; CLAUDE.md explicitly sanctions it for driving engines |
| Game termination rules in the arbiter | Manual repetition/50-move/insufficient-material logic | `board.is_game_over(claim_draw=True)` + `board.outcome(claim_draw=True)` | python-chess implements every adjudication rule correctly; Phase 2 tools already normalize outcomes this way |
| Engine-match orchestration at scale | Custom SPRT/Elo tournament manager | cutechess-cli / fastchess (when native runner desired), else keep the arbiter to W-L-D + Wilson CI | SPRT/Elo-with-error-bars is TOOL-04 (Phase 5) territory; Wilson CI satisfies D-19 with 6 lines of stdlib math |
| Opening book parsing | PGN tree walker | EPD/FEN lines + `chess.Board(fen)` (or `chess.pgn` if PGN chosen) | EPD sidesteps PGN parsing entirely for a fixed opening set |
| Statistical confidence | Bootstrap/simulation | Closed-form Wilson score interval | Exact requirement of D-19; standard formula |

**Key insight:** every "algorithm" in this phase (TT, killers, history, time budget) is a small, well-specified state machine — the libraries to lean on are the ones ANCE already has. The only genuinely new *external* surface is subprocess orchestration, which Phase 2 tools already prototype.

## Common Pitfalls

### Pitfall 1: Mate scores stored without node-relative conversion
**What goes wrong:** `score mate 3` at depth 5 becomes `mate 2`/`mate 4`/oscillating scores at depth 6+; gauntlet games where the engine shuffles instead of mating.
**Why it happens:** ANCE's tree scores are root-relative (`-(MATE - ctx.ply)` leaves); the same position reached at different plies then stores contradictory values.
**How to avoid:** Apply the store/probe ply adjustment in Pattern 1 in exactly one place (the TT module boundary), never in negamax itself.
**Warning signs:** D-22 test failing only for deeper searches; `mate N` that changes by ±1 between depths; TT-on vs TT-off disagreeing on mate positions.

### Pitfall 2: TT vs path-dependent draw detection (graph-history interaction)
**What goes wrong:** A position scored +300 and stored, later reached via a path where it's a repetition draw (or vice versa) — probe returns the wrong verdict.
**Why it happens:** Zobrist keys identify positions, not paths; repetition/50-move state is path data. CPW acknowledges GHI as unsolved-in-practice; every mainstream engine accepts the residual inaccuracy [CITED: chessprogramming.org/Transposition_Table related-topics].
**How to avoid:** (a) draw check before probe (locked); (b) pragmatic option at planner's discretion: skip storing scores that are exactly the repetition-draw 0 from `_is_draw_position` paths — but note leaf/stand-pat zeros are legitimate; simplest correct-enough policy is store-everything and accept GHI like everyone else.
**Warning signs:** Rare wrong evals only in shuffling endgames; do not chase these — verify criterion 1 (reproducible fixed-depth search from a cleared TT) instead.

### Pitfall 3: Hard-stop poll granularity exceeds the safety margin
**What goes wrong:** Engine flags despite a correct deadline: at 10k nps, `NODE_POLL_INTERVAL=2048` means up to ~200 ms between deadline checks, > the 150 ms margin.
**Why it happens:** The interval was tuned when only `movetime`/bare-go used deadlines and 2s budgets made 200 ms slop invisible.
**How to avoid:** Lower interval to ~512 (still ≤0.1% overhead in Python where a node costs ~20–100 µs) and set safety margin ≥ 200 ms. Verify with the blitz gauntlet at the *fastest* TC, not the most comfortable one.
**Warning signs:** Forfeits only in low-clock endgames; measured per-move overshoot beyond `hard_ms` in tests.

### Pitfall 4: Starting an ID iteration that can't finish (soft-limit gate missing)
**What goes wrong:** Under clock control the engine spends its whole budget on an aborted depth-d+1 iteration and moves with only depth-d information — or worse, at low clocks the hard stop truncates depth 1.
**Why it happens:** With EBF ~4–8, iteration d+1 costs several × iteration d; naive "search until hard deadline" wastes 60–85% of think time on discarded work.
**How to avoid:** Gate in `search_root`: don't start the next depth if `elapsed >= ~0.5 × soft_budget`. Keep a `MIN_BUDGET_MS` floor so depth 1 always runs.
**Warning signs:** `info` lines showing final completed depth unchanged from previous move despite long thinks; time usage per move ≈ hard limit every move.

### Pitfall 5: Ordering tables not shared across SearchContext clones and root moves
**What goes wrong:** TT/killers/history silently reset every child node or every root move; "ordering implemented" but node counts don't drop.
**Why it happens:** `_child_ctx` builds a new `SearchContext` per child, and `_search_at_depth` builds a fresh one per root move — new fields default-construct unless explicitly propagated (existing shared fields `counter`/`path_keys`/`game_history_keys` show the pattern).
**How to avoid:** Add `tt`/`killers`/`history` to `SearchContext`, propagate in `_child_ctx`, and source them from one per-search object created in `search_root` (TT itself from the per-process engine state). Write a RED test: nodes-to-depth-4 with TT must be < without.
**Warning signs:** D-21 benchmark shows no improvement; TT hit-rate counter near zero.

### Pitfall 6: Triple Zobrist computation per node
**What goes wrong:** 20–40% node-cost regression eats the ordering gains.
**Why it happens:** `_is_draw_position` computes `zobrist_hash`, then `path_keys.append(zobrist_hash(...))` computes it again (existing double-compute, verified in `negamax.py`); a TT probe/store adds a third and fourth. `chess.polyglot.zobrist_hash` is a full O(pieces) recompute, not incremental.
**How to avoid:** Compute the key once at node entry, pass it to the draw check, path push, probe, and store. This is also a free small speedup over Phase 2.
**Warning signs:** nps drops after the TT lands instead of staying flat.

### Pitfall 7: Stale worker writing tables during the bounded-join window
**What goes wrong:** A `go` preempts a worker that survives the 0.5s bounded join; old and new workers briefly run concurrently, both touching the shared TT.
**Why it happens:** Existing generation design tolerates a timed-out worker (output is generation-gated, but side effects aren't).
**How to avoid:** Nothing structural needed: with tuple entries and single-slot list assignment, writes are atomic under the GIL — worst case is a stale-but-well-formed entry, which the depth-preferred policy and full-key check tolerate. Document this; do NOT add locking to the per-node hot path.
**Warning signs:** None expected; if paranoid, assert entry well-formedness in a debug mode, never in the hot path.

### Pitfall 8: TT memory and `ucinewgame` clear cost assumptions
**What goes wrong:** Assuming the 2^20 table is "8 MB like in C". In CPython each filled entry is a ~5-tuple + boxed 64-bit key ≈ 150–250 bytes → up to ~250 MB when saturated.
**Why it happens:** C sizing intuition (16-byte entries) doesn't survive object headers.
**How to avoid:** Fine on 24 GB — but say so in the plan, and note `clear()` via list reallocation is O(size) ≈ tens of ms, acceptable at `ucinewgame` frequency only (never call it per-move).
**Warning signs:** Gauntlet RSS growth per game (means clear isn't wired); multi-hundred-ms `ucinewgame` stalls (means something slower than realloc was used).

### Pitfall 9: "Reproducible fixed-depth search" vs a warm TT
**What goes wrong:** Criterion 1 says fixed-depth search is reproducible, but a second identical `go depth N` on a warm TT returns different node counts (and can return a different-but-equal move via hash-move ordering).
**Why it happens:** The TT is deliberately persistent across `go` commands within a game.
**How to avoid:** Define reproducibility as *from a cleared state*: tests issue `ucinewgame` (or construct a fresh TT) before each measured search. Node-count baselines must state TT-cold.
**Warning signs:** Flaky determinism tests that pass in isolation and fail in suites.

### Pitfall 10: Gauntlet trusts engine-side clocks / underestimates runtime
**What goes wrong:** (a) D-14 "zero forfeits" is asserted but nothing measures forfeits (chess.engine doesn't); (b) the 100-game run is scheduled as an ordinary test and blows the suite budget by hours.
**Why it happens:** Assuming the library referees; assuming compiled-engine game speeds (Phase 2's measured reality: one depth-2-vs-3 80-halfmove game ≈ 540 s *without* clocks).
**How to avoid:** Arbiter-side clock accounting (Pattern 4); TC chosen so 100 games ≈ 2–4 h; `slow` marker + small smoke variant; record exact command line in SUMMARY (D-19).
**Warning signs:** A "passing" gauntlet with no forfeit counter in the report.

## Code Examples

### TT probe/store integration in `negamax()` (fail-soft, ply-adjusted)
```python
# Source: CPW Transposition Table semantics adapted to ance/search/negamax.py
def negamax(pos, depth, alpha, beta, ctx):
    ctx.counter[0] += 1
    _poll_stop(ctx)
    board = pos.board
    key = chess.polyglot.zobrist_hash(board)          # ONCE per node (Pitfall 6)
    if _is_draw_position_keyed(pos, ctx, key):        # draw check FIRST
        return 0
    if depth == 0:
        return quiescence_search(pos, alpha, beta, ctx)

    alpha_orig = alpha
    hash_move = None
    hit = ctx.tt.probe(key)
    if hit is not None:
        tt_depth, tt_score, tt_flag, tt_move = hit
        hash_move = tt_move
        score = tt_from_node_relative(tt_score, ctx.ply)   # mate ply adjustment
        if tt_depth >= depth:
            if tt_flag == EXACT: return score
            if tt_flag == LOWER and score >= beta: return score
            if tt_flag == UPPER and score <= alpha: return score

    ctx.path_keys.append(key)
    try:
        moves = pos.legal_moves()
        if not moves:
            return -(MATE - ctx.ply) if pos.is_check() else 0
        best, best_move = -MATE - 1, None
        for move in order_moves(moves, board, hash_move, ctx.killers[ctx.ply], ctx.history):
            board.push(move)
            try:
                score = -negamax(pos, depth - 1, -beta, -alpha, _child_ctx(ctx, ctx.ply + 1))
            finally:
                board.pop()
            if score > best:
                best, best_move = score, move
            if score >= beta:
                if not board.is_capture(move) and move.promotion is None:
                    update_killers(ctx.killers[ctx.ply], move)
                    ctx.history[int(board.turn)][move.from_square][move.to_square] += depth * depth
                break                                   # fail-soft cutoff
            if score > alpha:
                alpha = score
        flag = LOWER if best >= beta else (UPPER if best <= alpha_orig else EXACT)
        ctx.tt.store(key, depth, tt_to_node_relative(best, ctx.ply), flag, best_move)
        return best
    finally:
        ctx.path_keys.pop()
```
(Note: the current code returns on `score >= beta` inside the loop; converting to `break` so the store still runs is the one structural change — behavior-identical for the returned score.)

### Killer update
```python
# Source: CPW Killer Heuristic (two slots, shift-in)
def update_killers(slots: list, move) -> None:
    if move != slots[0]:
        slots[1] = slots[0]
        slots[0] = move
```

### Clock budget + soft gate wiring
```python
# handle_go clock branch (precedence preserved: infinite > depth > movetime > clock > bare default)
elif cmd.wtime is not None or cmd.btime is not None:
    soft_ms, hard_ms = compute_budget(cmd, pos.board.turn)   # Pattern 3 formula
    deadline = time.monotonic() + hard_ms / 1000
    # pass soft_ms/1000 to search_root as soft_budget

# search_root iteration gate
for depth in range(1, target_depth + 1):
    elapsed = time.monotonic() - start_time
    if soft_budget is not None and elapsed >= 0.5 * soft_budget and last_completed is not None:
        break
    ...
```

### cutechess-cli invocation the harness should generate when available
```bash
# Source: standard cutechess-cli usage (chessprogramming.org/Cutechess-cli); fastchess accepts the same shape
cutechess-cli \
  -engine name=ance-a cmd="$PY" arg="-m" arg="ance" \
  -engine name=ance-b cmd="$PY" arg="-m" arg="ance" \
  -each proto=uci tc=30+0.3 \
  -openings file=ance/tools/openings.epd format=epd order=sequential \
  -games 2 -rounds 50 -repeat \
  -draw movenumber=80 movecount=8 score=10 \
  -pgnout gauntlet.pgn
```
(`-games 2 -repeat` = each opening twice with colors swapped — the same parity D-16 requires; the arbiter fallback implements the identical scheme in Python.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Two-tier TT (depth-preferred + always-replace) | Single depth-preferred table is still standard for first TT; buckets are a later refinement | — | D-02 locks depth-preferred; buckets are out of scope |
| cutechess-cli as the universal match runner | fastchess (Disservin) is what Stockfish's own testing moved toward; cutechess 1.5.1 still maintained but ships no macOS binaries | fastchess mac-arm64 assets since ~v1.5-alpha; cutechess macOS assets absent as of 1.5.1 (2026-06) | On this Mac: python-chess arbiter default, fastchess the native option [VERIFIED: gh api release assets] |
| History = simple from/to accumulation | Top engines use CMH/follow-up/threat histories | ~2015+ | Out of scope — plain butterfly history is correct for D-09 and this strength band |
| `movestogo`-based budgeting | Sudden-death + increment formulas (remaining/N + inc credit) | UCI GUIs mostly send suddendeath+inc | Formula in Pattern 3; `movestogo` isn't parsed and isn't needed (lichess/cutechess send inc TCs) |

**Deprecated/outdated:** nothing in this phase's domain; these algorithms are stable since the 1990s. The only "freshness" risks were tooling availability, which was verified this session.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv (arm64) | everything | ✓ | 3.13 (`.venv`) | — |
| `chess` (python-chess) | board/TT keys/arbiter | ✓ | 1.11.2 | — |
| `pytest` (+ `slow` marker) | D-23 fast lane, benchmarks | ✓ | configured in pyproject | — |
| `cutechess-cli` | TOOL-03 primary runner (D-15) | ✗ — no brew formula, no macOS release asset (v1.5.1 ships win64 + Linux AppImage only) | — | **python-chess arbiter (mandatory fallback, D-15)**; optional fastchess |
| `fastchess` | optional native runner | ✗ (not installed; prebuilt `fastchess-mac-arm64.tar` exists, v1.8.0-alpha 2026-01-28) | — | arbiter |
| Stockfish | — (not needed Phase 3) | ✗ (`which` empty) | — | n/a this phase |
| Cute Chess GUI | — (GUI validation used En Croissant previously) | ✗ | — | En Croissant already in use per project memory |

**Missing dependencies with no fallback:** none — the mandatory path (arbiter) uses only installed software.
**Missing dependencies with fallback:** cutechess-cli → python-chess arbiter (default here); fastchess is a user-install option, never auto-downloaded.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed; `slow` marker registered in pyproject.toml) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/python -m pytest -m "not slow" -q` |
| Full suite command | `.venv/bin/python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-05 | Probe/store flags, depth-preferred replacement, full-key collision rejection | unit | `pytest tests/test_transposition_table.py -q` | ❌ Wave 0 |
| SRCH-05 | Mate-in-2/3 stable `score mate N` across depths (criterion 1, D-22) | unit/integration | `pytest tests/test_transposition_table.py -k mate -q` (reuse FENs from `test_tactical_search.py`) | ❌ Wave 0 |
| SRCH-05 | `ucinewgame` clears TT/killers/history (criterion 4) | integration | `pytest tests/test_uci_generation.py -k ucinewgame -q` or new file | ❌ Wave 0 |
| SRCH-06 | Ordering bands: hash > captures > killers > history; killer shift; history aging cap | unit | `pytest tests/test_move_ordering.py -q` | ❌ Wave 0 |
| SRCH-06 | Nodes-to-fixed-depth reduced vs no-ordering baseline (criterion 2, D-21) | benchmark (deterministic, TT-cold) | `pytest tests/test_phase3_strength_baseline.py -q` | ❌ Wave 0 |
| SRCH-08/UCI-08 | Budget formula invariants (hard ≤ remaining − margin; soft ≤ hard; floor; precedence D-13) | unit | `pytest tests/test_time_management.py -q` | ❌ Wave 0 |
| SRCH-08 | Never-flag under tight clocks (short in-process games with arbiter clocks) | integration (fast subset) + slow 100-game gauntlet (D-14, criterion 3) | fast: `pytest tests/test_time_management.py -k flag -q`; full: `pytest -m slow -k gauntlet` or `python -m ance.tools.gauntlet …` | ❌ Wave 0 |
| TOOL-03 | Harness runs N games from EPD book with color parity; W-L-D + Wilson CI; forfeit counter | unit (parity/CI math) + slow (100-game 50% sanity, criterion 5, D-17) | `pytest tests/test_gauntlet_harness.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest -m "not slow" -q` (D-23 mandate)
- **Per wave merge:** full fast suite + relevant new module tests
- **Phase gate:** full suite green + slow gauntlet evidence (100-game blitz zero-forfeit run and ~100-game 50% sanity run, recorded with exact command lines per D-19) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_transposition_table.py` — SRCH-05 (flags, replacement, mate ply, clear)
- [ ] `tests/test_move_ordering.py` — SRCH-06 (bands, killers, history)
- [ ] `tests/test_time_management.py` — SRCH-08/UCI-08 (budget math, precedence, poll granularity)
- [ ] `tests/test_gauntlet_harness.py` — TOOL-03 (parity, Wilson CI, forfeit accounting; smoke game count)
- [ ] `tests/test_phase3_strength_baseline.py` — D-20 baseline snapshot MUST be captured against the pre-TT code (i.e., recorded before/at the start of the first implementation wave)
- [ ] Framework install: none — pytest present

## Security Domain

This phase is a local, offline CLI program; most ASVS categories do not apply.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Existing UCI parser tolerance (malformed tokens skipped, D-11) must extend to garbage clock values: negative/zero `wtime` must clamp to the minimum budget, never crash or compute a negative deadline |
| V6 Cryptography | no | Zobrist is not cryptographic and needn't be |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess command injection in the gauntlet (engine command strings) | Tampering | Build argv lists (`[sys.executable, "-m", "ance"]`), never `shell=True`; established in `phase2_deterministic_evidence.py` |
| Runaway/zombie engine subprocesses on arbiter crash | DoS (local) | `try/finally engine.quit()` (or `SimpleEngine` context manager) + subprocess timeouts, per Phase 2 tool patterns |
| Unbounded memory growth (TT/history) across long gauntlets | DoS (local) | Fixed-size TT (D-01), history aging cap (D-09), `ucinewgame` clear (D-06) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Mate-score store/probe ply-adjustment formulas (score+ply on store / −ply on probe, Bruce Moreland convention) | Pattern 1 | Wrong `mate N` across depths — but the derivation is shown against ANCE's own leaf convention and D-22's tests empirically pin it; low residual risk |
| A2 | Expected node reduction 2–5× at depth 4–5 from ordering+TT; EBF ~4–8 remains | Patterns 2–3 | Only calibration numbers, not correctness; D-21's benchmark measures the real value |
| A3 | First-move-cutoff rate >85–90% as an ordering health signal | Pattern 2 | Diagnostic-only threshold |
| A4 | Arbiter IPC/parse overhead ~1–5 ms per move | Pattern 4 | If larger on this machine, the safety margin (200 ms) still dominates; measure in the smoke gauntlet |
| A5 | fastchess CLI is drop-in cutechess-compatible for this harness's argument subset | Pattern 4 / State of the Art | Only affects the *optional* native-runner path; arbiter is the default. Verify flags against fastchess `--help` if that path is exercised |
| A6 | 100-game blitz gauntlet runtime ≈ 2.5–4 h at 30+0.3 | Pattern 4 | Scheduling only; smoke run will recalibrate |
| A7 | Filled TT ≈ 150–250 MB at 2^20 tuple entries in CPython | Pitfall 8 | Ample headroom on 24 GB either way; measurable with `sys.getsizeof` spot checks if needed |

## Open Questions

1. **Should the harness treat fastchess as a first-class runner or cutechess-cli-only + arbiter?**
   - What we know: cutechess-cli is unavailable on this machine (verified); fastchess has a prebuilt mac-arm64 binary; the arbiter fallback fully satisfies TOOL-03 per D-15.
   - What's unclear: whether the user wants to install fastchess at all.
   - Recommendation: plan for `cutechess-cli` passthrough + arbiter default (both required by D-15); accept an optional `--runner <path>` that also works with a fastchess binary. Do not block on or auto-install anything.
2. **Blitz TC for the D-14 100-game gauntlet.**
   - What we know: pure-Python speeds make long TCs multi-hour; faster TCs prove the never-flag property harder.
   - What's unclear: exact TC the user prefers (CONTEXT says "blitz").
   - Recommendation: default 30+0.3 (or 10+0.1 for the smoke run); record final choice + command line in SUMMARY per D-19.
3. **Store-on-abort policy.**
   - What we know: `SearchAborted` unwinds through nodes mid-search; partial results at aborted nodes are not valid for their nominal depth.
   - What's unclear: nothing fundamental — just needs an explicit decision.
   - Recommendation: never `tt.store` on the abort path (the `raise` skips the store naturally if store sits after the move loop; verify with a test that a deadline-aborted search doesn't corrupt the table).

## Sources

### Primary (HIGH confidence)
- Installed codebase: `ance/search/negamax.py`, `ance/search/types.py`, `ance/uci/loop.py`, `ance/uci/parser.py`, `ance/tools/*` — all integration-point claims read directly this session
- Installed `chess` 1.11.2 source (`chess/engine.py` lines 1545–1556): `Limit(white_clock…)` → `go wtime…` translation; no forfeit adjudication [VERIFIED: venv source]
- GitHub Releases API via `gh`: cutechess v1.5.1 assets (win64 + AppImage only); fastchess v1.8.0-alpha assets (incl. `fastchess-mac-arm64.tar`) [VERIFIED: gh api]
- Local environment probes: `brew info cutechess` (no formula), `which cutechess-cli/fastchess/stockfish` (absent), pytest markers [VERIFIED: shell]

### Secondary (MEDIUM confidence)
- chessprogramming.org/Transposition_Table — flags, probe cutoff conditions, depth-preferred replacement, GHI acknowledgment [CITED, fetched]
- chessprogramming.org/Time_Management — soft/hard bound model, checked-per-iteration vs per-N-nodes [CITED, via search]
- chessprogramming.org/Killer_Heuristic, /History_Heuristic — slot and butterfly-table conventions [CITED, via search]
- mediocrechess.blogspot.com TT guide — EXACT/ALPHA/BETA store conditions [CITED, fetched]
- Context7 `/niklasf/python-chess` — engine-vs-engine play loop shape [CITED]

### Tertiary (LOW confidence)
- Calibration estimates flagged in the Assumptions Log (A2–A4, A6–A7) — training knowledge, marked [ASSUMED], each covered by a phase measurement

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages; everything verified installed
- Architecture (TT/ordering/clock algorithms): HIGH — decades-standard algorithms, cited; integration points verified by reading current source
- Mate-ply convention: MEDIUM — standard convention, derivation shown, empirically pinned by D-22 tests
- Tooling availability (cutechess/fastchess): HIGH for current facts — verified via GitHub API + brew this session; release assets can change
- Pitfalls: HIGH for codebase-derived ones (3, 5, 6, 9), MEDIUM for calibration ones

**Research date:** 2026-07-10
**Valid until:** ~2026-08-10 (stable domain; recheck only the cutechess/fastchess release-asset facts if the native-runner path is exercised)
