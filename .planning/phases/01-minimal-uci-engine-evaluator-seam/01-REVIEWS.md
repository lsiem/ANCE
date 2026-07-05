---
phase: 1
reviewers: [gemini, codex, cursor]
reviewed_at: 2026-07-05T17:41:47Z
plans_reviewed: [01-01-PLAN.md, 01-02-PLAN.md, 01-03-PLAN.md, 01-04-PLAN.md, 01-05-PLAN.md, 01-06-PLAN.md]
reviewers_failed: [antigravity]  # agy -p hung past timeout, no transcript persisted
reviewers_skipped: [claude, coderabbit]  # claude=self (running CLI); coderabbit=diff-only, no source code yet
---

# Cross-AI Plan Review — Phase 1: Minimal UCI Engine & Evaluator Seam

> Reviewed by 3 independent models. Skips: `claude` (self — this session's CLI), `coderabbit` (diff-only reviewer, no source code exists yet). Failed: `antigravity` (agy -p hung past the print timeout and persisted no transcript).

## Gemini Review

# Cross-AI Plan Review: ANCE Phase 1 — Minimal UCI Engine & Evaluator Seam

This review analyzes the 6-plan series (`01-01-PLAN.md` through `01-06-PLAN.md`) proposed for the initial walking skeleton, protocol plumbing, search substrate, and handcrafted evaluation of the ANCE chess engine.

---

## 1. Summary

The proposed phase plan is an exceptionally well-structured, logically sequenced, and disciplined approach to bootstrapping a chess engine from a greenfield repository. By splitting the phase into six discrete waves, the plans establish a rock-solid walking skeleton—proving non-blocking standard I/O and subprocess-driven testing—before introducing any complex chess logic or evaluation metrics. The strict architectural separation of search and evaluation via a formal `Evaluator` protocol is beautifully maintained throughout, and the test suite's design is highly creative, combining subprocess-level integration checks with targeted structural audits and precise value-level validation (such as PST orientation checks). Addressing minor threading edge cases and performance tuning for pure-Python execution will elevate this plan from great to production-grade.

---

## 2. Strengths

- **Superb Vertical Slicing & Dependency Order:** Starting with a pure protocol-level walking skeleton (handshake + first-legal-move selector) in Wave 1 ensures that any process I/O, piping, or OS-level threading quirks are diagnosed and resolved early, completely decoupling protocol integration from search correctness.
- **Strict Evaluator Decoupling:** The architecture boundary (D-00a) is enforced through a brilliant structural test that reads the AST/source of `ance/search/negamax.py` and asserts the total absence of concrete evaluator class names. This guarantees the "swappable evaluation module" value proposition remains real, not cosmetic.
- **Robustness at the Protocol Interface:** The design aggressively addresses common protocol failure modes by ignoring unknown leading tokens (D-11), rejecting malformed FENs/moves while keeping the previous board untouched (D-10) via a local copy-and-swap pattern, and always returning `bestmove (none)` in checkmate/stalemate to prevent GUI desynchronization.
- **Clever PST Orientation Checks:** Transcribing 64-square tables from diagram-space (rank 8 first) to array-space (index 0 = a1) is notoriously prone to vertical mirroring errors. The inclusion of a dedicated unit test asserting against "pinned reference cells" that are asymmetric under vertical mirroring is a highly professional detail.
- **Deterministic state reset validation:** Standardizing the tie-break RNG with a seedable generator and verifying that `ucinewgame` restores the exact RNG sequence ensures gauntlet games are fully reproducible and free of state-leak bugs.

---

## 3. Concerns

### [Severity: MEDIUM] Threading Race Conditions during Concurrent Searches
The main thread blocks on stdin and spawns a daemon thread for every `go` command. However, the plans do not explicitly specify how the engine behaves if a GUI sends a second `go` command (or a `position` command followed by `go`) while a search worker thread is actively running. If unguarded, the engine will spawn multiple concurrent search threads writing to `sys.stdout` simultaneously, which violates the UCI protocol and can crash or desynchronize real GUIs.

### [Severity: MEDIUM] Pure-Python Search Bottlenecks with Null-Move Mobility
With a branching factor of $\approx 35$, a depth-3 search evaluates $\approx 43,000$ leaf nodes. If the handcrafted evaluation's mobility term pushes a null-move and performs a second legal move generation at *every leaf*, the engine will perform over $86,000$ legal move generations per search. In pure Python, this can easily take 1.0–2.5 seconds on an M4 Mac, which risks violating the bare `go` sub-second performance constraint (D-02) even at depth 3, and makes depth 4 completely unusable.

### [Severity: LOW] Busy-Waiting or Blocking in the `go movetime` Dispatcher
In Plan 01-03 Task 3, it is stated that the `go` handler spawns a daemon thread running `search_root` inside a loop that checks the movetime deadline. If this deadline-checking loop is executed on the main thread, it will block the stdin reader, preventing the engine from responding to prompt incoming `stop` or `quit` commands.

### [Severity: LOW] King-only Stalemate Draw Risk in the Gauntlet
The random-mover gauntlet (Plan 01-05) asserts that ANCE wins exactly 100/100 games (draws fail the test). While ANCE's search substrate scores stalemate as `0` and checkmate as `+MATE` (actively avoiding stalemate when checkmate is available), a pure-Python engine without repetition or 50-move tracking in the search tree could theoretically fall into a draw loop if it shuffles its pieces on equal-best evaluations.

---

## 4. Suggestions

- **Implement Search Active Guards:** In `ance/uci/loop.py`, check if `worker` is not None and `worker.is_alive()` upon receiving a `go` command. If active, either set the `stop_flag` and wait for the thread to join before starting the new search, or safely ignore the duplicate command.
- **Use `threading.Timer` for Movetime Deadlines:** Instead of running a manual deadline checking loop or calling `time.monotonic()` repeatedly within the performance-sensitive search tree, use `threading.Timer(movetime_ms / 1000.0, stop_flag.set)` inside `handle_go` to trigger clean, asynchronous search cancellation.
- **Optimize Pawn Structure Checks with `int.bit_count()`:** When calculating pawn penalties (Plan 01-04 Task 3), leverage Python's native `int.bit_count()` method on bitwise-masked integers (e.g., `(int(pawns) & file_mask).bit_count()`) rather than string-parsing options like `bin().count()`, which can severely bottleneck pure-Python evaluations.
- **Profile Leaf Mobility Costs Early:** In Plan 01-04, establish a performance micro-benchmark for leaf-evaluation speed. If generating legal moves for the mobility term at every leaf degrades performance too severely, consider caching legal move counts, calculating pseudo-legal move differences instead, or falling back to a simpler mobility term under pure-Python search.

---

## 5. Risk Assessment

**Overall Risk: LOW**

### Justification:
The planning artifacts are incredibly thorough and technically sound. The technology stack choices (such as native Python 3.13, `python-chess`, and `pytest`) are stable, and the domain constraints are understood with expert-level clarity. The identified concerns are standard chess engine development bottlenecks rather than fatal architectural flaws, and they can be easily mitigated within the proposed modular architecture without altering the database schemas, protocols, or core module shapes. The risk of project desynchronization or implementation failure is exceptionally low.

---

## Codex Review

**Summary**

The plan set is strong: phased, test-driven, and tightly scoped to the “minimal UCI engine + evaluator seam” goal. It establishes the two hardest-to-retrofit decisions early (non-blocking UCI loop and the evaluate(position)->cp seam), uses python-chess correctly behind a narrow adapter, and wires a fixed-depth negamax substrate with reproducible tie-breaking. Coverage of robustness (reject-and-keep semantics, flush discipline, stop/quit behavior) is explicit, with sensible validation through subprocess tests and a manual GUI checkpoint. The main risks are concurrency edges around overlapping go/position/quit, a potentially brittle “100/100 vs random” target, and a few protocol nits (setoption swallowing, go infinite semantics) that can be hardened with small adjustments.

**Strengths**

- Phased TDD approach with clear artifacts and acceptance tests per wave.
- Clean Evaluator Protocol seam; search never depends on concrete eval classes.
- Non-blocking reader/worker model with Event-based cancellation and bounded join.
- Robust input handling: “reject-and-keep” for FEN/moves; info string for errors.
- UCI output hygiene: flush on every line; bestmove (none) for zero-legal-move cases.
- Deterministic tie-breaks via seedable RNG, reseeded on ucinewgame.
- Practical defaults: safe DEFAULT_DEPTH; sampled node polling; parse-but-ignore clock params.
- Tooling forethought: subprocess pytest harness, slow-marked gauntlet, manual GUI gate.

**Concerns**

- HIGH: Overlapping commands
  - New go while a search is already running; position sent mid-search; quit during send_bestmove. Without explicit preemption rules, duplicate or stale bestmove outputs are possible.
- MEDIUM: TOOL-02 brittleness
  - “100 wins out of 100” against a uniform random mover at shallow depth can be flaky (occasional stalemates or 50-move draws), especially with pure negamax and no QS/TT/ordering.
- MEDIUM: go infinite semantics
  - Computing to a fixed default depth then idling is acceptable for M1, but some GUIs expect a continuously “thinking” engine (normally via ID + info lines). With no info output (UCI-11 deferred), this can look inert longer than expected.
- MEDIUM: bestmove (none) compatibility
  - Most GUIs accept `(none)`, but some tools prefer `0000`. You’ve justified SF parity; still worth a fallback toggle to avoid surprises.
- MEDIUM: Mobility via null move
  - Using a null move for opponent mobility must be guarded carefully in positions where null is undesirable (e.g., in check). You note a guard; ensure it’s consistently applied to avoid evaluation artifacts.
- LOW: setoption swallowing
  - D-09 says zero options and tolerate setoption. Relying on generic “unknown token” skip can leave trailing tokens (“name … value …”) to be seen as new commands on the same line in some parsers. Better to add an explicit setoption handler that consumes the rest of the line.
- LOW: Mate score convention
  - Negamax returns flat -MATE/0 at terminals (good enough for M1). Ensure the Evaluator docstring stays strict about ±(MATE−ply) so future TT/ID won’t need a contract change.
- LOW: ucinewgame interaction with running search
  - Resetting board/RNG is good, but ucinewgame while a search is running should likely also signal stop to avoid a bestmove emitted for a stale position.

**Suggestions**

- Add explicit handlers:
  - setoption: accept and consume the rest of the line without side effects.
  - ponder/ponderhit: accept and no-op to avoid GUI warnings; they’re common even if unsupported.
- Preemption policy:
  - On receiving go while a worker is active: set stop_flag for the current worker immediately, join with a short timeout, then start the new worker. Add tests for “go/go” and “position/go while search running” to ensure exactly one bestmove per go.
  - On ucinewgame: also set stop_flag if a search is running.
- Hardening go infinite:
  - Keep current behavior (compute once then wait) but document it explicitly; consider emitting a minimal info string (“info string idle after depth D; waiting for stop”) when debug is on to aid GUI diagnosis without implementing UCI-11.
- bestmove (none) fallback:
  - Support an env-var or tiny flag to choose `0000` instead of `(none)` to maximize GUI compatibility without changing defaults.
- Random-mover gauntlet:
  - To reduce flakiness, run at depth 4 in the slow test and/or extend max_halfmoves; alternatively, assert “wins >= 98 and losses == 0” if you want deterministic CI yet stay faithful to the spirit. If you keep 100/100 strict, document how long it typically takes and what to tweak (depth, seed variety) if it fails on some machines.
- Mobility term:
  - Ensure the null-move guard is applied (return 0 opponent-mobility if in check). Optionally note the cost of extra movegen per leaf and keep MOBILITY_WEIGHT modest to limit runtime impact at DEFAULT_DEPTH.
- Minor protocol polish:
  - Confirm readyok is always issued immediately from the reader thread, regardless of state.
  - Ensure unknown tokens are fully consumed per line to avoid half-parsed leftovers; tests already cover this spirit.

**Risk Assessment**

- Overall: LOW-MEDIUM
- Rationale: Architecture and sequencing are sound with strong tests and clear phase boundaries. The main uncertainties are concurrency edge cases (multiple commands while searching) and the strictness of the 100/100 gauntlet under a shallow, non-pruned search. Both are addressable with small, localized adjustments and/or test tuning without touching core design decisions.

---

## Cursor Review

# Cross-AI Plan Review — Phase 1: Minimal UCI Engine & Evaluator Seam

## 1. Summary

This is a strong, well-sequenced greenfield plan set. The six-wave structure (walking skeleton → board adapter → search/eval seam → full handcrafted eval → gauntlet → GUI checkpoint) matches the phase boundary and the two hardest-to-retrofit decisions (non-blocking threading and the `Evaluator` Protocol). Requirements trace cleanly to plans, TDD tasks are concrete, and the research-derived pitfalls (flush discipline, D-10 reject-and-keep, clock-param tolerance, `bestmove (none)`) are addressed in the right places. Overall the plans should achieve the five phase success criteria, with a few threading/concurrency gaps and a performance-validation timing issue that could cause surprises after Plan 01-04.

## 2. Strengths

- **Correct foundational ordering.** Establishing the UCI loop and reader/worker model in 01-01 before real search (01-03) and eval (01-04) is the right call for D-00b/D-13.
- **Eval seam is real, not cosmetic.** Plan 01-03’s structural grep test (`negamax.py` must not reference concrete evaluators), plus Plan 01-04’s reinforcement after `HandcraftedEval`, directly supports success criterion 4 and NNUE drop-in later.
- **D-10 is implemented correctly.** Local candidate board, swap-on-success-only, and integration tests for malformed-FEN-keeps-board are well specified in 01-02.
- **UCI GUI compatibility is anticipated.** Parsing `wtime`/`btime`/`winc`/`binc` parse-and-ignore (01-03) addresses a common Cute Chess/Arena failure mode before TOOL-01.
- **Terminal positions handled explicitly.** `has_no_legal_moves()` → `search_root` returns `None` → `bestmove (none)` is wired through plans and tests (01-02, 01-03).
- **Pinned PST transcription strategy.** Using in-repo appendix values with orientation-sensitive reference cells (01-04 Task 1) reduces transcription risk without live web fetches during execution.
- **Proof points are separated appropriately.** TOOL-02 (automated 100/100 gauntlet, 01-05) and TOOL-01 (manual GUI, 01-06) are independent; wave-5 parallelization of 01-05 and 01-06 after 01-04 is sensible.
- **Test harness design.** Subprocess fixture with queued readline and timeout (01-01) avoids the classic “works in TTY, hangs when piped” trap.
- **Scope discipline is mostly good.** No alpha-beta, TT, quiescence, NNUE, or real clock budgeting leak into these plans; deferred items are explicitly called out.

## 3. Concerns

- **HIGH — No specification for overlapping `go` commands.** Plans describe spawning a worker per `go` but do not say what happens if a second `go` arrives before the first worker emits `bestmove` (common in GUIs and stress tests). Without joining/cancelling the prior worker or serializing searches, duplicate `bestmove` lines or races on shared `stop_flag`/evaluator state are plausible.
- **HIGH — Sub-second `bare go` benchmark runs before the expensive eval lands.** Plan 01-03 asserts bare `go` completes within 1.0s at `DEFAULT_DEPTH=3` using `MaterialEval`. Plan 01-04 adds per-leaf mobility (`legal_moves` + null-move opponent mobility) but does not re-benchmark or adjust `DEFAULT_DEPTH`. Success criterion 1 (GUI never hangs/timeouts) may fail after 01-04 even if 01-03 passes.
- **MEDIUM — D-11 interpretation may be oversimplified.** D-11 says skip the unknown *leading* token and attempt to parse the rest of the line; Plan 01-01/01-02 skip the entire unrecognized line (`continue`). That is safe for Phase 1 but is not spec-literal and could miss valid trailing tokens on malformed lines (low practical risk, but a spec fidelity gap).
- **MEDIUM — `movetime` deadline mechanism is underspecified.** Plan 01-03 says the worker runs `search_root` “inside a loop that also checks the movetime deadline,” but `search_root`/`negamax` only observe `stop_flag`. It is unclear whether a timer thread sets `stop_flag`, whether the outer loop re-invokes search, or whether deadline is polled only between root moves. Ambiguity here is a common source of flaky movetime tests.
- **MEDIUM — `isready` during active search is not explicitly tested.** Research notes `readyok` must come from the reader thread without waiting on the worker (UCI-02). The threading model implies this, but no plan task verifies `go` + delayed `isready` → immediate `readyok` while search runs.
- **MEDIUM — Mate scoring contract split between search and eval.** D-00a documents `evaluate()` mate as `±(MATE − ply)`, but Phase 1 negamax uses flat `-(MATE)`/`0` at terminal nodes and handcrafted eval never returns mate scores. Acceptable for Phase 1, but the plans should state explicitly that NNUE Phase 5 must either implement mate in `evaluate()` or search will remain the sole mate scorer — otherwise “zero search-side change” could break when mate propagation matters in Phase 2+.
- **MEDIUM — `position`/`ucinewgame` during an in-flight search.** Worker uses `pos.copy()`, so thread safety is OK, but behavior if the board changes while searching (stale bestmove for old position) is not defined. Most engines stop or ignore; worth a one-line policy.
- **LOW — Structural swap-seam test is brittle.** Grep for class name substrings in `negamax.py` can be gamed and won’t catch dynamic imports; sufficient for Phase 1, not a long-term guard.
- **LOW — Plan 01-01 skeleton lacks `stop`/`join` on `quit`.** Acceptable for wave 1 (trivial worker), but implementers should not carry that pattern into 01-03 without the join timeout described there.
- **LOW — Gauntlet draw cap at 300 half-moves.** Treating cap as `1/2-1/2` could theoretically fail strict `wins == 100` if a pathological line appears; unlikely vs random at depth 3 but worth monitoring in the slow test output.

## 4. Suggestions

- **Add a concurrency policy to Plan 01-03 (Task 3):** On new `go`, set `stop_flag`, `join()` prior worker with a short timeout, clear `stop_flag`, then spawn fresh worker. Add a test: `go depth 5` followed quickly by second `go depth 1` yields exactly two `bestmove` lines in order, no crash.
- **Re-benchmark after Plan 01-04:** Add a Task 4 (or extend 01-04 verification) that re-runs the bare-`go` sub-second check with `HandcraftedEval` wired in; tune `DEFAULT_DEPTH` to 2 if needed, documented inline.
- **Clarify movetime implementation:** Specify a single pattern — e.g. worker thread runs one `search_root`; main/reader or a small helper sets `stop_flag` when `time.monotonic() >= deadline` (same path as external `stop`). Avoid ambiguous “loop around search_root.”
- **Add `isready`-during-search test in 01-03:** After `go infinite`, send `isready` and assert `readyok` within 1s without waiting for `bestmove`.
- **Document D-11 choice explicitly:** Either align parser with “skip leading token only” or record a deliberate Phase 1 simplification (“ignore whole unknown lines”) in 01-02 must_haves so executors don’t debate it.
- **State terminal-draw policy for Phase 1:** Engine may continue playing in KvK etc. (legal moves exist); only checkmate/stalemate trigger `bestmove (none)`. Prevents implementers from expanding into draw detection prematurely.
- **Plan 01-05:** Log per-game results on failure (`seed`, FEN at termination, result string) so a rare non-win is diagnosable without re-running 100 games.
- **Plan 01-06:** Add a note to test with GUI time controls that send `wtime`/`btime` (not just movetime-only), since that path is the main GUI difference from pipe tests.

## 5. Risk Assessment

**Overall risk: MEDIUM**

**Justification:** Architecture and dependency ordering are sound; the eval seam and threading model are thoughtfully designed and test-backed for the common cases. The main execution risks are operational/concurrency edge cases (overlapping `go`, movetime wiring) and a performance cliff when handcrafted mobility lands after the sub-second benchmark — both can produce GUI hangs or timeouts despite green pytest. None of these look like fundamental design flaws; they are fixable with a few explicit policies and additional tests in Plans 01-03 and 01-04. The 100/100 random-mover goal is achievable at depth 3 with the specified eval, assuming search terminal scoring and legal movegen are correct.

---

## Consensus Summary

Three independent models (Gemini, Codex, Cursor) reviewed the 6-plan set. All three
converge on the same verdict: the architecture, sequencing, and test design are strong
and the plans should achieve the five phase success criteria — the risks are localized
concurrency edges and one performance-validation gap, not fundamental design flaws.
(Antigravity timed out/hung and produced no review; CodeRabbit was skipped — it is a
diff-only reviewer and this is a code-free planning phase.)

### Agreed Strengths (2+ reviewers)
- **Vertical slicing / dependency ordering** — walking skeleton (protocol + I/O + subprocess test harness) before search/eval is the right call; diagnoses OS/threading/pipe quirks early. *(all 3)*
- **The evaluator seam is real, not cosmetic** — the structural test asserting `negamax.py` references no concrete evaluator class directly backs success criterion 4 and NNUE drop-in. *(all 3)*
- **Robust protocol input handling** — D-10 reject-and-keep via local copy-and-swap, unknown-token tolerance, `bestmove (none)` for terminal positions. *(all 3)*
- **Pinned-PST + orientation-sensitive reference-cell tests** — catches the classic vertical-mirror transcription bug without a live web fetch. *(Gemini, Cursor)*
- **Deterministic tie-break RNG reseeded on `ucinewgame`** — reproducible gauntlet games, no state leak. *(Gemini, Codex)*
- **Subprocess test harness** avoids the "works in TTY, hangs when piped" trap. *(Gemini, Cursor)*
- **Scope discipline** — no alpha-beta / quiescence / TT / NNUE / real clock budgeting leaked in. *(Codex, Cursor)*

### Agreed Concerns (2+ reviewers — highest priority)
1. **[HIGH] No preemption policy for overlapping `go` / mid-search `position` / `ucinewgame`.** All three reviewers' #1 concern. A second `go` (or `position`/`ucinewgame`) arriving before the current worker emits `bestmove` can spawn concurrent search threads writing to stdout → duplicate/stale `bestmove`, GUI desync, races on shared `stop_flag`. **Fix:** on new `go`, set `stop_flag`, `join()` the prior worker with a short timeout, clear the flag, then spawn; on `ucinewgame`/`position` during search, also signal stop. Add tests: `go/go` and `position`-during-search each yield exactly one `bestmove` per `go`. *(Gemini, Codex, Cursor)*
2. **[MEDIUM–HIGH] Performance cliff after Plan 01-04.** The sub-second bare-`go` benchmark runs in 01-03 with the cheap `MaterialEval`, but 01-04 adds per-leaf mobility (extra legal-move generation + null-move) and never re-benchmarks or re-tunes `DEFAULT_DEPTH`. Success criterion 1 (GUI never hangs/times out) can fail after 01-04 even though 01-03's test passed green. **Fix:** re-run the sub-second check with `HandcraftedEval` wired in as an 01-04 verification step; tune `DEFAULT_DEPTH` (down to 2 if needed) and document inline. *(all 3)*
3. **[MEDIUM] TOOL-02 `100/100` gauntlet brittleness.** A uniform random opponent at shallow, non-pruned depth can occasionally draw (stalemate / 50-move / repetition), and strict `wins == 100, losses == 0` treats any draw as failure. **Fix (options):** run the slow test at depth 4 and/or raise the halfmove cap; or relax to `wins >= 98 and losses == 0`; and log per-game `seed`/terminal-FEN/result on failure so a rare non-win is diagnosable without rerunning all 100. *(all 3)*
4. **[MEDIUM] `movetime` deadline mechanism underspecified.** It is unclear whether a timer thread sets `stop_flag`, an outer loop re-invokes search, or the deadline is polled only between root moves — and a deadline loop on the reader thread would block `stop`/`quit`. **Fix:** pin one pattern — worker runs a single `search_root`; a `threading.Timer(movetime/1000, stop_flag.set)` (same cancellation path as external `stop`) fires the deadline. *(Gemini, Codex, Cursor)*
5. **[MEDIUM] Mobility null-move guard.** Pushing a null move for opponent mobility must be skipped when the side to move is in check (null move is illegal/undesirable there). Ensure the guard is applied consistently to avoid eval artifacts; keep `MOBILITY_WEIGHT` modest given the per-leaf movegen cost. *(Gemini, Codex)*
6. **[MEDIUM] Mate-scoring contract split.** Phase 1 negamax scores terminals flat (`-MATE`/`0`) while the D-00a seam documents `±(MATE − ply)`. Fine for M1, but the plans should state explicitly that search remains the sole mate scorer so Phase 5's "zero search-side change" NNUE swap doesn't silently break when mate propagation matters. *(Codex, Cursor)*
7. **[LOW–MEDIUM] `setoption`/`ponder` swallowing & D-11 fidelity.** Relying on a generic unknown-token skip can leave trailing `name … value …` tokens to be misparsed; D-11's "skip only the leading token" is implemented as "skip the whole line." **Fix:** add an explicit `setoption` (and no-op `ponder`/`ponderhit`) handler that consumes the rest of the line, or record the whole-line skip as a deliberate M1 simplification in must_haves. *(Codex, Cursor)*

### Divergent Views
- **Overall risk rating:** Gemini **LOW**, Codex **LOW–MEDIUM**, Cursor **MEDIUM** — the spread is entirely about how much weight to give the concurrency/perf edges; all three agree they're localized and fixable without touching core design.
- **Structural swap-seam grep test:** Gemini praised it as "professional"; Cursor flagged it as brittle/gameable (won't catch dynamic imports) — LOW. Both agree it's sufficient for Phase 1.
- **`bestmove (none)` vs `0000`:** only Codex raised adding a `0000` fallback toggle for maximum GUI compatibility; the pinned SF-parity choice (D-12) is otherwise unchallenged.
- **`go infinite` looking inert:** only Codex flagged that with UCI-11 (`info` output) deferred, a compute-once-then-idle engine may look inert to some GUIs; suggests a debug-only idle `info string`.

### Recommended action
The two HIGH-consensus items (overlapping-`go` preemption policy, re-benchmark after the eval lands) are worth folding into the plans before execution — both land in Plan 01-03/01-04 and are small, localized additions. The rest are good hardening notes the executor can apply in place. Feed this back with `/gsd-plan-phase 1 --reviews`.
