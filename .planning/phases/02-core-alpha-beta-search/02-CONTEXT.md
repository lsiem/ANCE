# Phase 2: Core Alpha-Beta Search - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The engine plays real, tactically sound chess via **iterative-deepening fail-soft
negamax** with **quiescence search**, correct **draw/terminal handling**, and
full **`info depth … pv …`** output each completed iteration — while keeping the
Phase 1 `evaluate(position)->cp` seam and non-blocking reader/worker model intact.

**In scope:** alpha-beta pruning on the existing negamax skeleton; iterative
deepening with root best-move tracking across depths; quiescence (captures +
queen promotions, stand-pat + delta pruning, MVV-LVA inside qsearch only);
twofold-in-search draw detection + 50-move + insufficient material; terminal
mate/stalemate scoring with ply-adjusted mate propagation; UCI `info` lines per
completed depth; default `go` movetime budget (~2s soft); `go infinite` deepens
until `stop`; folded TOOL-02 depth-4 gauntlet + tactical/mate-in-N pytest suite
+ depth-vs-depth self-play mini-match as strength evidence.

**Out of scope (later phases — do NOT build here):** Zobrist transposition table
(SRCH-05, Phase 3); full move ordering in main search (hash/killers/history,
SRCH-06, Phase 3); real `wtime/btime/winc/binc` clock parsing (SRCH-08/UCI-08,
Phase 3); NNUE eval and training (Phases 4–5). Main search stays **unordered**
(except qsearch MVV-LVA) so Phase 3's ordering baseline comparison stays honest.
</domain>

<decisions>
## Implementation Decisions

### Locked upstream (carried forward — do NOT re-open)
- **D-00a:** Eval seam `evaluate(position) -> centipawns`, side-to-move relative,
  mate as ±(MATE − ply) once scores propagate through search. *(Phase 1 D-00a)*
- **D-00b:** Non-blocking reader/worker threading; `stop`/`quit` honored mid-search.
  *(Phase 1 D-00b)*
- **D-00c:** Board state, movegen, repetition helpers via `python-chess`; hand-written
  UCI loop. *(Phase 1 D-00c)*

### Folded todos
- **D-01:** Fold deferred **TOOL-02** depth-4 gauntlet into Phase 2 strength
  validation. Target: `losses == 0` (hard) with improved win-rate at
  `GAUNTLET_SEARCH_DEPTH >= 4`, wall-clock budget **≤ 10 minutes** for the
  100-game run. If cap-draws persist at depth 4, escalate to depth 5 within
  budget; if still cap-draws, pass on `losses == 0` + improved win-rate,
  document evidence, keep 100/0 as Phase 3 target.

### Quiescence design
- **D-02:** At quiet nodes (not in check): examine **captures + queen promotions**
  only — no checks in qsearch at quiet nodes.
- **D-03:** Bound qsearch with **stand-pat + delta pruning**.
- **D-04:** **MVV-LVA capture sort inside qsearch only**; main search remains
  unordered until Phase 3.
- **D-05:** When side to move is **in check**: search **all evasions**, no
  stand-pat; zero evasions scores mate.

### Draw handling in search
- **D-06:** **Twofold-in-search = draw**: position occurring in game history or
  earlier in the current search path scores **0** immediately (transposition-key
  stack comparison).
- **D-07:** Draw score is **plain 0**, no contempt.
- **D-08:** **50-move rule** (`halfmove_clock >= 100`) and **insufficient material**
  both via `python-chess` helpers; mate-beats-clock exception preserved.

### ID behavior & info output
- **D-09:** Bare `go` (no depth/movetime/clock): **default movetime budget (~2s
  soft)** — iterate deeper until budget expires, return last completed depth's
  best. Real clock parsing stays Phase 3.
- **D-10:** **Drop Phase 1 random tie-break RNG (D-04)** — deterministic PV;
  first-best-found wins ties; previous iteration's best searched first.
- **D-11:** **One `info` line per completed depth** (`depth`, `score cp|mate`,
  `nodes`, `nps`, `pv`). Aborted partial iterations emit nothing; last completed
  depth's line matches `bestmove`.
- **D-12:** `go infinite`: deepen until `stop` (up to MAX_PLY cap), info per
  completed depth, bestmove from last completed iteration. Supersedes Phase 1
  D-16 idle behavior; fixes En Croissant "Unlimited" hang.

### Strength validation
- **D-13:** Beyond the folded gauntlet: **mate-in-N + tactical pytest suite**
  — fixed FENs asserting `score mate N` + mating move, hanging-piece/fork tactics
  found, qsearch horizon cases not misplayed.
- **D-14:** Verify "deeper search never plays measurably worse" via **depth-vs-depth
  self-play mini-match** (~30–50 games; deeper side must score ≥ 50%), reusing
  Phase 1 arbiter harness.
- **D-15:** Gauntlet fallback (D-01): if depth-4 still cap-draws within budget,
  escalate depth then judge per folded-todo policy.

### Claude's Discretion
- Exact `MAX_PLY` cap for `go infinite`.
- Default movetime constant tuning (~2s target).
- Internal qsearch depth cap / extension policy details.
- ~~Mate score ply-adjustment implementation specifics~~ — superseded by D-18
  below (round-2 addendum): the wire format is now a locked decision.

### Round-2 decisions (post-planning addendum, 2026-07-08)

> Captured in a second discussion round AFTER `docs(02): create phase 2 …
> plans` was committed and execution began in a parallel session. D-16/D-17
> match what was built; D-18/D-19 are gaps filed as pending todos
> (`resolves_phase: 2`) that must close before the phase verifies.

- **D-16:** **Evolve `ance/search/negamax.py` in place** — no parallel
  alpha-beta module; the structural seam test keeps guarding the real search.
  *(✅ already matches the executed implementation, incl. the `types.py` split.)*
- **D-17:** **Time expiry aborts mid-iteration** via the existing
  `NODE_POLL_INTERVAL` poll; answer from the last completed depth.
  *(✅ already matches the executed implementation — `deadline` checks in
  `negamax.py`.)*
- **D-18:** **Mate scores on the wire are FULL MOVES, signed** —
  `score mate y` with `y = ceil((MATE − |score|) / 2)`, negative when being
  mated — per the UCI spec and Stockfish convention (gauntlet log
  comparability). A mate window (`|score| ≥ MATE − MAX_PLY` is fine as the
  classifier) separates mate from cp scores, and evaluator cp output must be
  clamped below that window so no eval can masquerade as mate.
  *(❌ gap: `ance/uci/protocol.py::send_info_depth` currently emits the raw
  ply distance — mate-in-3-plies prints `mate 3` instead of `mate 2`. See
  `.planning/todos/pending/2026-07-08-uci-mate-score-full-moves.md`.)*
- **D-19:** **Phase 2 closes with a watched En Croissant validation game**
  (like Phase 1's 01-06): live game with `info` depth/score/pv visible in the
  GUI, fixed time-per-move preset (never "Unlimited" until D-12's fix is
  confirmed working there).
  *(❌ gap: no plan schedules this. See
  `.planning/todos/pending/2026-07-08-phase2-encroissant-validation.md`.)*

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §Phase 2 — goal, success criteria, dependency on Phase 1
- `.planning/REQUIREMENTS.md` — SRCH-02, SRCH-03, SRCH-04, SRCH-07, UCI-11

### Phase 1 locked decisions & artifacts
- `.planning/phases/01-minimal-uci-engine-evaluator-seam/01-CONTEXT.md` — D-decisions
  (eval seam, threading, negamax substrate, D-04 RNG to drop, D-16 infinite idle)
- `.planning/phases/01-minimal-uci-engine-evaluator-seam/01-05-SUMMARY.md` — gauntlet
  replan rationale and measured depth-2 evidence
- `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md` — folded
  TOOL-02 scope (now in Phase 2)

### Source anchors
- `ance/search/negamax.py` — Phase 1 fixed-depth negamax skeleton to extend
- `ance/eval/base.py` — Evaluator Protocol, MATE constant, seam contract
- `ance/tools/random_mover_gauntlet.py` — gauntlet harness (depth target to raise)
- `tests/test_random_mover_gauntlet.py` — gauntlet acceptance tests

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ance/search/negamax.py`: fixed-depth negamax with `SearchAborted`, node polling,
  terminal leaf scoring — bolt alpha-beta, ID, and qsearch onto this skeleton.
- `ance/eval/base.py`: `Evaluator` Protocol + `MATE`; search becomes sole mate
  scorer with ply-adjusted propagation in Phase 2.
- `ance/tools/random_mover_gauntlet.py` + `tests/test_random_mover_gauntlet.py`:
  existing gauntlet harness; raise `GAUNTLET_SEARCH_DEPTH` when alpha-beta makes
  depth ≥ 4 practical.
- Phase 1 UCI worker/search dispatch: non-blocking `stop_flag`, `search_generation`
  gating — preserve when layering ID.

### Established Patterns
- Evaluator seam: search imports only `Evaluator` Protocol, never concrete eval classes.
- Side-to-move-relative centipawn scores throughout.
- `python-chess` for board ops; hand-written UCI protocol loop.
- Sampled `stop_flag` polling (`NODE_POLL_INTERVAL`) — keep for ID/qsearch scale.

### Integration Points
- `search_root` → extend for iterative deepening loop, root PV tracking, info emission.
- UCI `go` handler → map bare `go` to soft movetime budget; `go infinite` to ID-until-stop.
- Draw detection hooks at interior nodes before move expansion.

</code_context>

<specifics>
## Specific Ideas

- En Croissant "Unlimited" (`go infinite`) should deepen and emit info, not idle-hang.
- Phase 3 needs an honest unordered-main-search baseline — do not pre-install full
  move ordering in main search.
- Variety at root comes from opponent/opening book, not RNG tie-breaks.

</specifics>

<deferred>
## Deferred Ideas

- **v1.1 local web-app GUI** (existing backlog todo) — not folded into Phase 2.
- **100/0 at depth 4 with zero draws** — stretch goal; may defer to Phase 3 if
  cap-draws persist after depth escalation within budget.

</deferred>

---

*Phase: 02-Core Alpha-Beta Search*
*Context gathered: 2026-07-08*
