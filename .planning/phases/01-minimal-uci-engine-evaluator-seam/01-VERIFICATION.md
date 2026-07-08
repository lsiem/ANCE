---
phase: 01-minimal-uci-engine-evaluator-seam
verified: 2026-07-08T13:52:52Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "The engine beats a random-mover opponent 100 games out of 100."
    reason: "TOOL-02 formally REPLANNED 2026-07-07 (human-approved, recorded in .planning/REQUIREMENTS.md line 53): losses==0 hard invariant + wins>=70% floor + every non-win a draw. The original 100/100-at-depth-4 target was measured impractical (depth-4/100-game run killed after 31 min unpruned) and is DEFERRED, not deleted (pending todo 2026-07-07-tool-02-depth-4-gauntlet-deferred.md)."
    accepted_by: "user (lasse)"
    accepted_at: "2026-07-07T00:00:00Z"
deferred:
  - truth: "ANCE beats the random mover 100/0 (zero draws) at depth 4"
    addressed_in: "Phase 2/3"
    evidence: "Phase 2 SC1: 'fail-soft negamax alpha-beta and iterative deepening' — the pruning that makes depth 4 wall-clock-practical; Phase 3 goal includes 'the self-play gauntlet harness'. Tracked in .planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md."
---

# Phase 1: Minimal UCI Engine & Evaluator Seam — Verification Report

**Phase Goal:** A GUI-playable UCI engine that never hangs, routes every leaf through a swappable `evaluate(position)->cp` seam, and plays a full legal game with a handcrafted eval.
**Verified:** 2026-07-08T13:52:52Z
**Status:** passed
**Re-verification:** No — initial verification
**Mode:** mvp (phase goal verified against the delivered user-facing outcome: a GUI-playable engine)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Engine completes the `uci`/`isready` handshake in a GUI and plays a full legal game to a natural result without hanging or being disqualified | ✓ VERIFIED | Human-witnessed live in **En Croissant** (mac-native GUI, 2026-07-08): ANCE-vs-ANCE over real UCI pipes via `~/.local/bin/ance-uci`, full clean legal game to a natural result, no hang/crash/illegal move (01-UAT.md test 5, pass). Supplemented by the external python-chess arbiter run (01-06-SUMMARY.md): Game 2 `go movetime 500` — 108 plies, 0-1 CHECKMATE, slowest move 0.60 s; Game 1 under a 5+2 clock — 48 plies, threefold repetition, no timeout/DQ. Note: SC text names Cute Chess/Arena; no macOS Cute Chess build exists (verified in 01-06-SUMMARY.md key-decisions), and the user accepted En Croissant as the literal-GUI validation. |
| 2 | A piped `position … / go / stop` script always returns exactly one legal `bestmove` promptly — even mid-search and in mate/stalemate/zero-legal-move positions (stdout flushed) | ✓ VERIFIED | Behavioral: spot-check this verification — piped fool's-mate FEN + `go depth 2` returned `bestmove (none)` (D-12 wire format, ance/uci/protocol.py:37) and exit 0. Fast suite (51 passed, 6.7 s): `test_zero_legal_move_position_returns_bestmove_none`, `test_stop_is_prompt_during_go_infinite`, `test_quit_never_deadlocks_during_go_infinite`, `test_stale_generation_worker_never_emits_bestmove_after_being_superseded`, `test_go_movetime_timer_cancelled_on_preemption_does_not_stop_next_search`, `test_bare_go_completes_under_a_second_with_handcrafted_eval` (~0.53 s < 1.0 s). Session evidence: `go wtime/btime` and `go movetime` return promptly (~0.5 s at depth 3); `go infinite` correctly waits for `stop`. Wiring: reader thread never searches (ance/uci/loop.py:291-303); `go` spawns a daemon worker (loop.py:167-182) gated by the monotonic `search_generation` counter (loop.py:129-136) so a superseded worker's result is dropped, never raced onto stdout. |
| 3 | The engine beats a random-mover opponent 100 games out of 100 | PASSED (override) | Override: TOOL-02 REPLANNED 2026-07-07 with human approval — REQUIREMENTS.md line 53 now reads "never loses (losses==0), wins ≥70%, every non-win a draw". Measured green this session (slow gauntlet re-run, ~30 s): **0 losses, ≥70% wins at depth 2**, all non-wins draws (max_halfmoves cap conversions). Harness is real and wired: ance/tools/random_mover_gauntlet.py `run_gauntlet()` drives the actual `search_root` + `HandcraftedEval` in-process, alternates colors, hard-asserts losses==0 (`test_ance_never_loses_and_wins_majority_vs_random_mover`, tests/test_random_mover_gauntlet.py:55). The 100/0-at-depth-4 target is deferred to the pruning phases (see frontmatter `deferred`). ROADMAP.md SC3 text is stale vs. the approved REQUIREMENTS.md contract — see Anti-Patterns/Info. |
| 4 | Swapping the evaluator behind the `evaluate(position)->cp` seam (side-to-move relative) changes only the eval — no search-side change required | ✓ VERIFIED | Seam exists and is substantive: `Evaluator` Protocol at ance/eval/base.py:24-39 (cp, side-to-move relative, `MATE=30000` shared sentinel). Search depends only on the Protocol: ance/search/negamax.py:31 imports `MATE, Evaluator` from `ance.eval.base` and calls `evaluator.evaluate(pos)` at every depth-0 leaf (negamax.py:75, "THE seam") — no concrete evaluator name appears in the module, proven structurally by `test_negamax_module_never_imports_a_concrete_evaluator` (pass). Swap proven with two real evaluators: `test_evaluator_swap_handcrafted_vs_material_no_negamax_change` (pass). Wired: `HandcraftedEval` is the live default at ance/uci/loop.py:68. |
| 5 | `position fen <malformed>` is rejected without crashing, and `ucinewgame` resets per-game state cleanly | ✓ VERIFIED | Behavioral spot-check: `position fen this-is-garbage` → `info string invalid position command, board unchanged`, engine continued and exited 0. Reject-and-keep contract implemented in the adapter (candidate built locally, committed only on success — 01-02 pattern) and exercised by `test_try_set_fen_rejects_malformed_fen_and_leaves_board_untouched`, `test_malformed_fen_rejected_board_unchanged`, `test_try_push_uci_moves_rejects_illegal_move_and_leaves_board_untouched` (all pass). `ucinewgame`: handle_ucinewgame (loop.py:223-229) stops/joins any active worker, resets to startpos, reseeds the tie-break RNG from ANCE_SEED (D-17) — `test_ucinewgame_resets_board_to_startpos`, `test_ucinewgame_reseeds_tie_break_rng`, `test_ucinewgame_during_active_search` (all pass). |

**Score:** 5/5 truths verified (4 direct + 1 via human-approved override; 0 present-but-behavior-unverified)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | 100 wins / 0 draws vs. random mover at depth 4 | Phase 2/3 | Phase 2 SC1 delivers alpha-beta pruning + iterative deepening (the prerequisite that makes depth 4 practical — depth-4 unpruned measured >31 min/100 games); Phase 3 delivers the gauntlet harness. Tracked: .planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `ance/uci/loop.py` | Non-blocking UCI reader/dispatch loop with preemption policy | ✓ VERIFIED | 307 lines, substantive. Reader thread only reads stdin; daemon search workers; `_stop_active_worker()` (stop→join→clear→cancel-timer) shared by go/position/ucinewgame/quit; `search_generation` gating drops stale bestmoves; module-scope `movetime_timer` cancelled on preemption and in the worker's finally block. Wired as the `python -m ance` entry point. |
| `ance/search/negamax.py` | Fixed-depth negamax routing every leaf through the seam | ✓ VERIFIED | 133 lines. `evaluator.evaluate(pos)` at every depth-0 leaf (line 75); sampled stop-flag polling (NODE_POLL_INTERVAL=2048) + per-root-move check; seeded tie-break RNG; `None` on zero legal moves (UCI layer converts to `bestmove (none)`). Imports only the `Evaluator` Protocol. |
| `ance/eval/base.py` | `Evaluator` Protocol — the swap seam | ✓ VERIFIED | `typing.Protocol` with `evaluate(pos: Position) -> int`, cp side-to-move relative; `MATE=30000` shared sentinel; Phase 1 mate-scoring tradeoff explicitly documented (base.py:30-38), not hidden. |
| `ance/eval/handcrafted.py` | Real handcrafted evaluator wired as default | ✓ VERIFIED | 165 lines. Michniewski Simplified Evaluation Function material+PSTs (ance/eval/tables.py) with discrete mg/eg king-table switch, mobility (null-move idiom with in-check guard, handcrafted.py:132-139), bishop-pair, tempo, doubled/isolated-pawn terms; white-relative composition with single sign flip (handcrafted.py:163, D-07). Wired: default evaluator at loop.py:68. Data flows: 12 eval-seam tests exercise real scores (e.g. `test_startpos_evaluates_to_exact_tempo_bonus`, `test_pst_reference_cells_match_pinned_appendix`). |
| `ance/tools/random_mover_gauntlet.py` | Self-play gauntlet vs. random mover (TOOL-02) | ✓ VERIFIED | 199 lines. `RandomMover`, `play_game()` (max_halfmoves=300 termination guarantee), `run_gauntlet()` with color alternation, non-win diagnostics list, and an in-code failure runbook distinguishing losses (always a bug) from sub-floor wins. Wired: driven by tests/test_random_mover_gauntlet.py; slow gauntlet green this session. |
| `ance/board/position.py`, `ance/uci/parser.py`, `ance/uci/protocol.py`, `ance/debug.py` | Position adapter, command parsing, wire formatting, stderr debug channel | ✓ VERIFIED | All exist and are exercised by the 51-test fast suite; `send_bestmove(None)` emits `bestmove (none)` (protocol.py:37); debug channel is stderr-only, off by default (`test_debug_off_by_default_no_stderr_output` pass). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ance/uci/loop.py` | `ance/search/negamax.py` | `handle_go` → daemon worker → `search_root` | WIRED | loop.py:44 imports `DEFAULT_DEPTH, search_root`; worker target `_run_search` calls `search_root` exactly once (loop.py:120). |
| `ance/search/negamax.py` | `ance/eval/base.py` (seam only) | `evaluator.evaluate(pos)` at every leaf | WIRED | negamax.py:31 imports only `MATE, Evaluator`; leaf call at negamax.py:75. Structural test proves no concrete evaluator name in the module. |
| `ance/uci/loop.py` | `ance/eval/handcrafted.py` | `evaluator: Evaluator = HandcraftedEval()` module default | WIRED | loop.py:43,68 — the one place a concrete evaluator is chosen, i.e. the swap point. |
| `ance/tools/random_mover_gauntlet.py` | `search_root` + `Evaluator` | in-process `play_game`/`run_gauntlet` | WIRED | gauntlet.py:52,100 — drives the real search and a real evaluator, not a mock. |
| `search_root` returning `None` | `bestmove (none)` on the wire | `_run_search` → `send_bestmove(None)` | WIRED | loop.py:131 + protocol.py:37; behavioral proof: fool's-mate spot-check emitted `bestmove (none)`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Fast suite green | `.venv/bin/python -m pytest -q -m "not slow"` | 51 passed, 1 deselected, 6.73 s | ✓ PASS |
| Handshake + malformed FEN + mate-position go + quit | piped `uci/isready/position fen <garbage>/position fen <fool's mate>/go depth 2/quit` | `uciok`, `readyok`, `info string invalid position command, board unchanged`, `bestmove (none)`, exit 0 | ✓ PASS |
| Slow gauntlet (TOOL-02) | re-run this session (verified evidence, not re-executed here per instruction) | 0 losses, ≥70% wins, ~30 s | ✓ PASS |
| Clock/movetime/infinite go modes | session-verified evidence | `go wtime/btime` and `go movetime` return bestmove ~0.5 s at depth 3; `go infinite` waits for `stop` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| UCI-01, UCI-02, UCI-12 | 01-01 | ✓ SATISFIED | Handshake + isready-during-search + quit-never-deadlocks tests pass (test_uci_handshake.py, test_go_bestmove.py:207,139). |
| UCI-03, UCI-04, UCI-05, SRCH-01 | 01-02 | ✓ SATISFIED | position/ucinewgame/malformed-rejection/terminal-detection tests pass (test_position_command.py; `has_no_legal_moves` uses checkmate/stalemate only). |
| UCI-06, UCI-07, UCI-09, UCI-10, EVAL-01 | 01-03 | ✓ SATISFIED | go depth/movetime/infinite/stop/quit + Evaluator Protocol seam; generation-gated bestmove (test_go_bestmove.py:229). |
| EVAL-02 | 01-04 | ✓ SATISFIED | HandcraftedEval default with pinned PSTs (reference-cell tests pass); sub-second bare go re-benchmarked. |
| TOOL-02 | 01-05 | ✓ SATISFIED (as replanned) | losses==0 / ≥70% wins / non-wins draws — green this session. REQUIREMENTS.md marks it Complete with the replan note. |
| TOOL-01 | 01-06 | ✓ SATISFIED | En Croissant live GUI game (2026-07-08, human-witnessed) + python-chess external arbiter games. **Note:** REQUIREMENTS.md line 52/112 still shows TOOL-01 as unchecked/Pending — stale bookkeeping, should be flipped to Complete. |

No orphaned requirements: all 15 IDs ROADMAP maps to Phase 1 are claimed by exactly the six plan summaries.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TODO/FIXME/XXX/TBD/placeholder/stub patterns in `ance/` (grep clean) | — | — |
| .planning/ROADMAP.md | 26, 44 | SC3 / phase one-liner still read "beats a random mover 100/100" — stale vs. the human-approved TOOL-02 replan codified in REQUIREMENTS.md | ℹ️ Info | Documentation drift only; the authoritative requirement contract (REQUIREMENTS.md) and the deferred todo are consistent. Recommend updating the ROADMAP SC text. |
| .planning/ROADMAP.md | 48, 70 | "Plans: 4/6 executed" and 01-06 unchecked, but 01-06-SUMMARY.md exists with `status: complete` | ℹ️ Info | Stale plan-tracking checkboxes; no code impact. |
| .planning/REQUIREMENTS.md | 52, 112 | TOOL-01 still unchecked/Pending despite this session's completed En Croissant GUI validation and UAT 5/5 | ℹ️ Info | Bookkeeping lag; flip to Complete. |

### Human Verification Required

None outstanding. The one inherently human item — watching a full legal game in a real GUI (TOOL-01 / SC1) — was completed and passed in 01-UAT.md (5/5, updated 2026-07-08T13:49:59Z): the user watched ANCE-vs-ANCE play a full clean legal game to a natural result live in En Croissant with no hang, crash, or illegal move.

### Gaps Summary

No gaps. All five success criteria are observably true in the codebase: the non-blocking loop and generation-gated preemption are implemented exactly as claimed (verified by reading loop.py/negamax.py, not by trusting the summaries), the seam is a real `typing.Protocol` with a structural no-concrete-import proof and two live evaluators demonstrating the swap, malformed input is rejected without crash (behaviorally re-proven in this verification), and the phase's behavior-dependent truths (stop/preemption/stale-bestmove-drop, mate/stalemate `bestmove (none)`) all have passing behavioral tests rather than presence-only evidence. The single deviation from the literal ROADMAP text — SC3's 100/100 gauntlet — is a formally approved, documented replan (REQUIREMENTS.md) with the stricter-than-it-looks invariant "never loses, ≥70% wins, every non-win a draw" measured green, and the original target tracked as a deferred todo owned by the pruning phases.

---

_Verified: 2026-07-08T13:52:52Z_
_Verifier: Claude (gsd-verifier)_
