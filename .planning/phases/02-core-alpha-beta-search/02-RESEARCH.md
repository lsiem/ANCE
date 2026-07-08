# Phase 2: Core Alpha-Beta Search — Research

**Researched:** 2026-07-08
**Confidence:** HIGH (extends Phase 1 patterns; standard chess-engine algorithms)

## Summary

Phase 2 layers fail-soft alpha-beta negamax, quiescence, iterative deepening, draw detection, and UCI `info` output onto the existing `ance/search/negamax.py` skeleton and `ance/uci/loop.py` worker model. No new dependencies; `python-chess` helpers cover draw detection. Main search stays unordered (Phase 3 baseline); MVV-LVA applies only inside qsearch per D-04.

## Standard Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Search core | Fail-soft negamax α-β in `negamax.py` | Extends Phase 1 skeleton; SRCH-02 |
| Qsearch | Stand-pat + delta pruning, captures + queen promos | D-02, D-03; SRCH-04 |
| ID loop | Root `search_root` iterates depths 1..N | SRCH-03; keeps last completed depth on stop |
| Draw detection | Twofold-in-search stack + `board.is_fifty_moves()` + `board.is_insufficient_material()` | D-06–D-08; SRCH-07 |
| Position keys | `chess.polyglot.zobrist_hash(board)` for repetition stack | Already in python-chess; no hand-rolled Zobrist TT |
| UCI info | `send_info_depth()` in `protocol.py` | UCI-11; one line per completed depth |
| Time budget | `time.monotonic()` soft deadline for bare `go` (~2s) | D-09; real clock parsing deferred Phase 3 |

## Architecture Patterns

### Pattern 1: SearchResult return type

`search_root` evolves from `chess.Move | None` to a `SearchResult` dataclass carrying `best_move`, `score`, `depth`, `pv`, `nodes`. UCI layer reads fields for `info` + `bestmove`; gauntlet reads `best_move` only.

### Pattern 2: SearchContext (mutable per-root-search state)

Single object passed through negamax/qsearch: `stop_flag`, node `counter`, `evaluator`, `ply`, `path_keys` (list of zobrist hashes for twofold-in-search), `game_history_keys` (from root position), `deadline` (monotonic or None), `info_callback` (optional, for ID info lines).

### Pattern 3: Fail-soft alpha-beta

```text
score = negamax(child, depth-1, -beta, -alpha, ctx)
score = -score  # negamax flip
if score >= beta: return score  # fail-high (fail-soft: still return beta cutoff score)
if score > alpha: alpha = score
```

### Pattern 4: Ply-adjusted mate

Terminal checkmate at `ply` plies from root: `-(MATE - ply)` from side-to-move perspective before negamax child flip. Propagates so UCI `score mate N` reports plies to mate from root.

### Pattern 5: Qsearch boundary

At `depth == 0`: if in check, search all evasions (no stand-pat). If quiet: stand-pat eval, delta-prune captures+queen promotions sorted MVV-LVA, recurse with `depth` unchanged (or internal qdepth cap — discretion).

## Don't Hand-Roll

| Problem | Use Instead | Why |
|---------|-------------|-----|
| 50-move / insufficient material | `board.is_fifty_moves()`, `board.is_insufficient_material()` | D-08; python-chess is authoritative |
| Legal move generation | `Position.legal_moves()` | Phase 1 adapter |
| Position hashing for repetition | `chess.polyglot.zobrist_hash(board)` | Correct, fast enough without TT |
| UCI stdout flushing | `flush=True` on every print | Phase 1 pitfall |

## Common Pitfalls

1. **Horizon effect without qsearch** — fixed-depth leaves hang pieces; qsearch must run at depth-0 quiet nodes (D-02).
2. **Stand-pat in check** — forbidden per D-05; zero evasions = mate.
3. **RNG tie-break at root** — D-10 removes it; update `test_search_root_tie_break_uses_seeded_rng` and `test_ucinewgame_reseeds_tie_break_rng`.
4. **`go infinite` idle hang** — Phase 1 D-16 idles after one search; Phase 2 D-12 deepens until `stop`.
5. **Main-search move ordering** — do NOT add killers/history/hash move in main search (Phase 3 honest baseline).
6. **Aborted partial depth** — D-11: no `info` line for incomplete iterations; `bestmove` from last *completed* depth.

## Package Legitimacy Audit

No new packages this phase. Existing: `python-chess`, stdlib only.

| Package | Status | Notes |
|---------|--------|-------|
| python-chess | VERIFIED | Phase 1 dependency |
| (none new) | — | — |

## Architectural Responsibility Map

| Tier | Module | Responsibility |
|------|--------|----------------|
| Search | `ance/search/negamax.py` | α-β, qsearch, ID, draw cuts, mate scoring |
| Search | `ance/search/types.py` (new) | `SearchResult`, `SearchContext` |
| UCI | `ance/uci/loop.py` | `go` mode dispatch, worker thread, stop/infinite |
| UCI | `ance/uci/protocol.py` | `send_info_depth()` formatter |
| Tools | `ance/tools/random_mover_gauntlet.py` | Folded TOOL-02 depth-4 gauntlet |
| Tools | `ance/tools/depth_vs_depth_match.py` (new) | D-14 mini-match harness |
| Tests | `tests/test_alpha_beta.py`, `tests/test_quiescence.py`, `tests/test_iterative_deepening.py`, `tests/test_uci_info.py`, `tests/test_tactical_search.py` | Nyquist coverage |

## Validation Architecture

| Behavior | Test file | Marker |
|----------|-----------|--------|
| α-β prunes (node count bound) | `tests/test_alpha_beta.py` | fast |
| Mate ply propagation | `tests/test_alpha_beta.py` | fast |
| Qsearch captures horizon | `tests/test_quiescence.py` | fast |
| ID keeps last completed depth | `tests/test_iterative_deepening.py` | fast |
| Twofold/50-move/insuff. material | `tests/test_iterative_deepening.py` | fast |
| UCI info line format + pv[0]==bestmove | `tests/test_uci_info.py` | fast |
| Tactical FENs + mate-in-N | `tests/test_tactical_search.py` | fast |
| Depth-4 gauntlet losses==0 | `tests/test_random_mover_gauntlet.py` | slow |
| Depth-vs-depth ≥50% | `tests/test_depth_vs_depth.py` | slow |

## Open Questions (Claude's Discretion)

- `MAX_PLY` for infinite: recommend 64 (sufficient for GUI analysis).
- Default bare-go movetime: 2000ms soft target.
- Qsearch internal depth cap: 8 plies from leaf.
