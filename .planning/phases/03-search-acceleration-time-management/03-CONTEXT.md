# Phase 3: Search Acceleration & Time Management - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

The engine becomes **clock-safe and search-efficient**: a Zobrist transposition
table, full main-search move ordering, real `wtime/btime/winc/binc` time
management, and a reusable **self-play gauntlet harness** — while preserving
the Phase 1 eval seam, Phase 2 search correctness, and non-blocking UCI model.

**In scope:** SRCH-05 (TT), SRCH-06 (ordering), SRCH-08 + UCI-08 (clock),
TOOL-03 (cutechess-style gauntlet harness); `ucinewgame` clears per-game search
state; strength proof vs Phase 2 baseline at equal time.

**Out of scope (later phases — do NOT build here):** NNUE eval/training
(Phases 4–5); LMR/null-move/pruning extensions; aspiration windows; ponder;
`nodes`/`searchmoves` UCI limits; Phase 5 eval-swap gauntlet (TOOL-04 uses this
harness but is not Phase 3's deliverable).
</domain>

<decisions>
## Implementation Decisions

### Locked upstream (carried forward — do NOT re-open)
- **D-00a–D-00c:** Eval seam, reader/worker threading, `python-chess` board
  adapter, hand-written UCI loop. *(Phases 1–2)*
- **D-02–D-08, D-18–D-19:** Qsearch design, draw/terminal contracts, info
  output, mate wire format. *(Phase 2)*
- **D-10:** Deterministic tie-break (first legal / prior-iteration root move).
  *(Phase 2)*

### Transposition table (SRCH-05)
- **D-01:** **Fixed-size TT** starting at **2^20 entries (~1M)**; entry =
  `{key, depth, score, flag, best_move}`; pure-Python list/dict or compact
  array — planner chooses, size is the locked budget.
- **D-02:** **Depth-preferred replacement**: replace when empty or incoming
  depth ≥ stored depth; never shallow-over-deep.
- **D-03:** **Bound flags** EXACT / LOWER / UPPER with fail-soft alpha-beta
  semantics; probe cutoffs only when depth and bounds allow.
- **D-04:** **Mate scores** stored and retrieved with **ply adjustment**
  (same convention as negamax leaf mate scoring).
- **D-05:** **Zobrist key** = `chess.polyglot.zobrist_hash(board)` (consistent
  with Phase 2 path/history keys).
- **D-06:** **`ucinewgame` clears the entire TT** — no cross-game leakage
  (ROADMAP success criterion 4).

### Move ordering (SRCH-06)
- **D-07:** Main-search order: **TT hash move → MVV-LVA captures → killers →
  history heuristic → remaining quiet moves**. Qsearch keeps **MVV-LVA only**
  (Phase 2 D-04 unchanged).
- **D-08:** **Two killer slots per ply**; cleared on `ucinewgame`.
- **D-09:** **History heuristic** (from/to or move-index table); age or clear
  on `ucinewgame` — planner picks representation; table must not grow without
  bound across a game.
- **D-10:** TT best move feeds hash-move slot; killers updated on beta cutoffs
  at non-PV nodes (standard heuristic — exact cutoff policy is planner discretion).

### Clock management (SRCH-08 / UCI-08)
- **D-11:** **`GoCommand` already parses clock fields** (`ance/uci/parser.py`);
  Phase 3 **acts on** `wtime`/`btime`/`winc`/`binc` when present and `movetime`
  is absent.
- **D-12:** **Soft budget** = function of remaining side time + increment
  credit (simple divide-by-estimated-moves-left or urgency curve — planner
  chooses formula); **hard stop** with **≥150ms safety margin** before flag fall.
- **D-13:** Precedence unchanged: explicit **`movetime`** or **`depth`** or
  **`infinite`** overrides clock budgeting (Phase 2 behavior preserved).
- **D-14:** **Never lose on time** is a hard acceptance gate: **100-game blitz
  gauntlet** with clock fields must report **zero time forfeits**.

### Gauntlet harness (TOOL-03)
- **D-15:** **Primary runner: `cutechess-cli`** when available on PATH (e.g.
  `brew install cutechess`); **fallback: python-chess external arbiter** with
  the same opening book and UCI clock args — macOS has no Cute Chess GUI binary,
  but CLI may still be installable; fallback must not block Phase 3 completion.
- **D-16:** **Fixed opening book** (PGN or EPD subset) shared across both sides;
  deterministic seed / game-index parity for color (reuse Phase 2 depth-match
  patterns where applicable).
- **D-17:** **Sanity gauntlet:** handcrafted vs handcrafted, **~100 games**,
  score ≈ **50% ± noise** (validates harness, not eval strength).
- **D-18:** Harness API must support **two engine commands/builds differing only
  in eval** later (Phase 5); Phase 3 proves the plumbing with identical eval.
- **D-19:** Report **W-L-D + draw rate + optional Wilson 95% CI** on score
  percentage; record exact CLI/arbiter command lines in SUMMARY.

### Strength proof vs Phase 2 baseline
- **D-20:** **Snapshot Phase 2 baseline** before TT/ordering land: completed
  depth and nodes at **2s movetime** on a fixed FEN set (store artifact or test
  constants).
- **D-21:** Phase 3 must show **measurably greater completed depth or fewer
  nodes to same depth** at equal 2s budget vs baseline (pytest benchmark, not
  hand-waved).
- **D-22:** **Mate-in-2/3 positions** report stable **`score mate N`** across
  increasing depths once TT is warm (ROADMAP criterion 1).
- **D-23:** Re-run **fast pytest suite** (`-m "not slow"`) after each plan; no
  regression in Phase 2 draw/qsearch/UCI contracts.

### Claude's Discretion
- Exact TT entry layout and probe/store cutover conditions.
- History table dimensions and aging policy.
- Clock urgency formula details inside D-12 margin.
- Whether cutechess or arbiter is default on CI vs dev machine.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & requirements
- `.planning/PROJECT.md` — M4 Mac constraints, pure-Python ceiling, gauntlet strategy
- `.planning/REQUIREMENTS.md` — SRCH-05, SRCH-06, SRCH-08, UCI-08, TOOL-03
- `.planning/ROADMAP.md` — Phase 3 success criteria (5 items)
- `.planning/phases/02-core-alpha-beta-search/02-CONTEXT.md` — search contracts, out-of-scope fence
- `.planning/phases/02-core-alpha-beta-search/02-VERIFICATION.md` — Phase 2 passed baseline

### Code integration points
- `ance/search/negamax.py` — TT probe/store, ordering hooks, iterative deepening
- `ance/search/types.py` — SearchContext extensions for TT/killers/history
- `ance/uci/parser.py` — GoCommand clock fields already parsed
- `ance/uci/loop.py` — deadline wiring, ucinewgame reset
- `ance/tools/random_mover_gauntlet.py` — prior gauntlet patterns
- `ance/tools/depth_vs_depth_match.py` — color/opening parity patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `parse_go()` / `GoCommand`: clock ints parsed but ignored — wire into `handle_go` deadline.
- `SearchContext` in `negamax.py`: extend with TT pointer, killer/history tables.
- `depth_vs_depth_match.py` / `random_mover_gauntlet.py`: game loops, parity seeds, outcome tallying.
- `phase2_deterministic_evidence.py`: bounded evidence pattern for CI-friendly proofs.

### Established Patterns
- Zobrist via `chess.polyglot.zobrist_hash` already used for draw path keys.
- Generation-gated UCI output and worker preemption (Plan 02-08) — clock stop must use same `stop_event`.
- TDD RED/GREEN atomic commits per plan task.

### Integration Points
- TT probe at negamax entry after draw check; store on exit with bound flag.
- `handle_ucinewgame`: clear TT + killers + history (not just startpos).
- New `ance/tools/` gauntlet module wrapping cutechess or arbiter subprocess.

</code_context>

<specifics>
## Specific Ideas

- User approved full draft across TT, ordering, clock, gauntlet, and baseline proof (2026-07-10).
- Prefer installable `cutechess-cli` on macOS but **do not block** on it — python-chess arbiter fallback is mandatory.
- 100-game blitz for on-time proof; 50% sanity for identical-eval harness validation.

</specifics>

<deferred>
## Deferred Ideas

- **Aspiration windows / LMR / null-move pruning** — strength beyond ordering+TT; future milestone.
- **Statistical Elo / 1000+ game gauntlet (TOOL-04)** — Phase 5 after NNUE swap.
- **Collector artifact source-identity hash** — evidence harness hardening; optional tooling plan.
- **nodes limit / searchmoves / ponder** — UCI params parsed or skipped only.

</deferred>

---

*Phase: 03-search-acceleration-time-management*
*Context gathered: 2026-07-10*
