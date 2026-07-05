# Pitfalls Research

**Domain:** UCI chess engine (classical alpha-beta search + supervised NNUE evaluation) in pure Python, PyTorch/MPS on Apple Silicon M4
**Researched:** 2026-07-05
**Confidence:** HIGH (corroborated against `official-stockfish/nnue-pytorch` docs, Stockfish wiki, PyTorch MPS issue tracker, and UCI protocol conventions; MEDIUM only where noted for M4/macOS-version-specific behavior)

> Scope note: This file deliberately skips the strategic caveats the user already knows (self-play infeasible on M4, MPS is beta, pure-Python caps strength, Elo pools aren't interchangeable). Every entry below is an **implementation-level trap** with a concrete detection signal and fix. Milestones: **M1** = UCI loop, **M2** = alpha-beta search, **M3** = supervised NNUE.

---

## Critical Pitfalls

### Pitfall 1: Searching on the main thread blocks `stop` and stdin (engine "hangs")

**What goes wrong:**
The engine reads `go`, calls `search()` synchronously, and only returns to the read loop when search finishes. While searching it cannot read `stop`, `isready`, or `quit`. In a GUI/match the arbiter's `stop` is ignored, the engine blows its time budget, and Cute Chess reports a loss on time or "engine crashed / no response".

**Why it happens:**
The obvious single-threaded loop (`for line in sys.stdin: handle(line)`) couples "think" and "listen". Beginners assume the GUI waits politely; it does not — it can send `stop` mid-`go` and expects a `bestmove` promptly after.

**How to avoid:**
Run search in a worker thread (or `asyncio` task). The main loop only ever reads a line and dispatches. Search polls a shared `threading.Event` (`stop_flag`) at every node (or every N nodes) and returns the best move found so far when set. `stop` sets the flag; search must then emit `bestmove` regardless of depth. Never do blocking work in the reader thread.

**Warning signs:**
`stop` produces no `bestmove`; engine keeps printing `info` after `stop`; GUI shows the clock running to zero; a manual `echo -e "position startpos\ngo\nstop"` pipe never prints `bestmove`.

**Phase to address:** M1 (architect the loop as reader-thread + search-thread from day one; retrofitting threading after search exists is painful).

---

### Pitfall 2: Not flushing stdout / never emitting `bestmove`

**What goes wrong:**
The engine computes the move but the GUI never sees it because stdout is block-buffered when piped (not a TTY). Or a code path (`go` with `mate`/`nodes` limit, illegal state, search returns None) exits without printing `bestmove`. Either way the GUI stalls until it times out.

**Why it happens:**
Python buffers stdout aggressively when stdout is a pipe. And there are many `go` sub-cases; it's easy to have one that falls through.

**How to avoid:**
`print(..., flush=True)` on **every** UCI output line, or run with `python -u` / `sys.stdout.reconfigure(line_buffering=True)` at startup. Guarantee exactly one `bestmove` per `go`: even with zero legal moves emit `bestmove (none)`; if search is interrupted before completing depth 1, still return *some* legal move (do a 1-ply fallback before entering iterative deepening). Treat "every `go` produces exactly one `bestmove`" as an invariant with an assertion in tests.

**Warning signs:**
Works in an interactive terminal but hangs when driven by Cute Chess/a pipe; intermittent hangs at game start or in forced/mate positions.

**Phase to address:** M1.

---

### Pitfall 3: Mishandling `position ... moves` (state corruption)

**What goes wrong:**
Common variants: (a) not rebuilding the board from scratch each `position` command, so leftover state from the previous position leaks in; (b) applying the `moves` list to the wrong base (fen vs startpos); (c) parsing UCI moves incorrectly for promotions (`e7e8q`) or castling (`e1g1`); (d) treating the incremental `position startpos moves e2e4 e7e5 ...` as needing incremental undo when the safest correct behavior is to reset and replay. Result: engine analyzes a different position than the GUI thinks, plays a plausible-but-illegal-in-context move, and loses.

**Why it happens:**
`position` is stateless from the GUI's view — it resends the full move list each turn. Engines that try to "diff" the move list against the previous one introduce bugs; engines that mutate a persistent board without resetting accumulate errors.

**How to avoid:**
On every `position`: construct a fresh `chess.Board()` (or `Board(fen)`), then `board.push_uci(m)` for each move in order. Let `python-chess` do move parsing/legality — do not hand-roll UCI move parsing. Reserve incremental make/unmake for the *search tree*, not the root position setup. Log/echo the resulting FEN behind a debug flag and diff it against the GUI.

**Warning signs:**
Engine plays a legal-but-nonsensical move; `board.is_legal()` assertions fire mid-game; promotions or castling desync the position.

**Phase to address:** M1.

---

### Pitfall 4: Time-loss forfeits from naive time management

**What goes wrong:**
Engine allocates too much time per move (or ignores `wtime/btime/winc` entirely), or the "check the clock" logic only runs between depth iterations — so a single deep iteration overshoots and flags. Under `movetime` it starts a new deep iteration it can't finish. Losing on time is the #1 way a *correct* engine still loses rated games.

**Why it happens:**
Time is checked at the wrong granularity, or the allocation formula is missing increment handling, or iterative deepening starts iteration D+1 without asking "can I plausibly finish this before my soft limit?"

**How to avoid:**
Two-limit scheme: a **soft limit** (don't *start* a new ID iteration past it) and a **hard limit** (abort the current search immediately, ~2–3× soft). Check the hard limit inside the node loop every ~1024–4096 nodes (not every node — `time.monotonic()` has cost), not only between iterations. Baseline allocation: `alloc ≈ remaining / moves_to_go + increment*0.8`, with `moves_to_go` defaulting to ~25–30 when not given. Reserve a fixed safety margin (e.g. 50 ms) for output/latency. Honor `movetime`, `depth`, `nodes`, and `infinite` (search until `stop`).

**Warning signs:**
Losses recorded as "on time"; `nps` fine but games lost from winning positions; overshoot spikes on tactical positions where a deep iteration balloons.

**Phase to address:** M2 (search-side time control), wired to M1 parsing of `go` params.

---

### Pitfall 5: Transposition-table mate scores not adjusted for ply (THE classic TT bug)

**What goes wrong:**
Mate scores are stored as `MATE - ply_from_root`. If you store/probe that value in the TT without adjusting for the ply at which it is *reused*, a "mate in 3 from here" gets reported as "mate in 3" at a different depth, producing wrong PVs, oscillating mate announcements, and — worse — the engine either fails to convert forced mates or hallucinates mates that aren't there. This is one of the most common subtle correctness bugs in a first engine.

**Why it happens:**
Mate scores are relative to the root distance, but the TT is indexed by position (which recurs at different plies via transposition). A score correct at ply 7 is wrong when the same entry is hit at ply 4.

**How to avoid:**
On **store**: if `score >= MATE_BOUND`, store `score + ply`; if `score <= -MATE_BOUND`, store `score - ply`. On **probe**: reverse it — subtract/add `ply` to recover a root-relative score. Use a clear `MATE = 30000`-ish sentinel with a `MATE_BOUND = MATE - MAX_PLY` threshold to detect mate scores. Unit-test with known forced-mate FENs (mate-in-1/2/3) and assert the reported `score mate N` is stable across depths and correct.

**Warning signs:**
`score mate N` flickers between iterations; engine "sees" a mate then loses it; fails standard mate suites (e.g. reports mate but doesn't deliver it, or plays around a mate it announced).

**Phase to address:** M2. **This is a required checklist item (see quality gate).**

---

### Pitfall 6: Incorrect TT bound flags (EXACT / LOWER / UPPER) and cutoffs

**What goes wrong:**
Storing every node as EXACT, or mixing up alpha/beta bound semantics, causes the TT to return values that are only valid as bounds as if they were exact. Symptoms: search returns a move that isn't actually best, PVs that don't match the score, non-reproducible results at fixed depth, and "search instability" (same position, different answer depending on move order into it).

**Why it happens:**
Fail-hard vs fail-soft confusion; forgetting that a beta-cutoff yields only a *lower bound* (score ≥ beta) and an all-node (no move raised alpha) yields only an *upper bound*. Also: using a TT value for a cutoff when the stored `depth` is shallower than the current remaining depth.

**How to avoid:**
Store `flag = EXACT` only when `alpha < score < beta` (a PV node that raised alpha but didn't cut); `LOWER` (beta cutoff, `score >= beta`); `UPPER` (`score <= alpha_orig`). On probe, only trust the entry for a cutoff if `entry.depth >= remaining_depth` **and** the bound is compatible with the current window (`LOWER` allows `score>=beta`, `UPPER` allows `score<=alpha`). Always still allow the stored move to be tried first for ordering even when the score can't be used. Keep the TT move-ordering benefit separate from the score-cutoff logic.

**Warning signs:**
Fixed-depth search gives different bestmoves on repeat runs; disabling the TT changes the move (it should change speed, not correctness, modulo move-ordering effects); PV move disagrees with reported score.

**Phase to address:** M2.

---

### Pitfall 7: Quiescence search explosion / non-termination

**What goes wrong:**
Quiescence search (qsearch) with no restriction on which moves it considers, or that also searches checks/check-evasions unboundedly, explodes: node counts blow up 10–100×, `nps` craters, and in pathological positions qsearch effectively never returns, tripping the time hard-limit every move. Alternatively, an over-pruned qsearch misses obvious recaptures and the engine hangs pieces (the horizon effect).

**Why it happens:**
Qsearch is meant to only resolve "noisy" positions (captures, promotions, maybe checks). Including quiet moves, or checks without a depth cap, removes the natural termination (running out of captures).

**How to avoid:**
Standard qsearch: stand-pat (evaluate the position; if `stand_pat >= beta` return beta; set `alpha = max(alpha, stand_pat)`), then search **only captures and promotions** (optionally check-giving moves for the first 1–2 qsearch plies with a hard qsearch depth cap). Add **delta pruning**: skip a capture if `stand_pat + captured_piece_value + margin < alpha`. Order qsearch captures by MVV-LVA. Never generate quiet moves in qsearch. Cap qsearch check-extensions to avoid infinite check chains.

**Warning signs:**
Node count per move in the millions at low nominal depth; `nps` collapses in tactical positions; time hard-limit triggers constantly; engine hangs pieces to a "just past the horizon" recapture.

**Phase to address:** M2.

---

### Pitfall 8: Wrong checkmate/stalemate scoring and sign

**What goes wrong:**
Returning `0`/eval for a checkmated node instead of a large negative mate score, or scoring stalemate as a loss/win instead of a draw, or getting the perspective sign wrong (negamax expects scores from the side-to-move's POV). Result: the engine walks into mate, avoids stalemating a lost opponent incorrectly, or evaluates terminal nodes with the wrong sign and plays actively worse the deeper it searches.

**Why it happens:**
Terminal detection is a special case that's easy to bolt on wrong, and negamax sign conventions are a frequent source of off-by-a-negation bugs.

**How to avoid:**
At a node with no legal moves: if `board.is_check()` return `-MATE + ply` (side to move is mated — bad for them), else return `0` (stalemate = draw). Everything in negamax is from the side-to-move's perspective; `evaluate()` must return `+` = good for the side to move, and the recursion uses `-search(...)`. Write terminal-node unit tests: a mate-in-1 must be found at depth 1; a stalemate position must score exactly 0; a "mated in 0" node returns `-MATE + ply`.

**Warning signs:**
Engine avoids winning captures, plays into mate, or the deeper it searches the *worse* it plays (a smell for a sign error); scores that grow without bound or have inverted sign vs the board.

**Phase to address:** M2.

---

### Pitfall 9: Repetition and 50-move-rule draws not detected in search (or detected too expensively)

**What goes wrong:**
Two failure modes: (a) The engine doesn't detect threefold repetition / 50-move / insufficient material inside the search, so it thinks it's winning by repeating and either draws a won game or fails to claim/avoid a draw correctly. (b) It calls `python-chess`'s full `board.is_repetition()` / `can_claim_draw()` at every node — these are relatively expensive and tank `nps`.

**Why it happens:**
Draw-by-repetition is a *path* property, not a position property, so it interacts awkwardly with a position-keyed TT. And the convenient library calls are correct but slow for hot-loop use.

**How to avoid:**
Maintain your own lightweight stack of Zobrist/position keys as you make/unmake moves. Detect an in-search repetition cheaply by scanning back through the current line to the last irreversible move (capture/pawn move) — a **twofold** repetition within the search tree can be scored as a draw (0) for search purposes (contempt aside). Track the halfmove clock; return draw score at 100 halfmoves. Handle insufficient material. Do **not** store repetition-drawn nodes' scores in the TT as if position-only (path-dependence makes them unsafe to reuse). Reserve `python-chess`'s `can_claim_draw()` for the *root* claim decision, not per-node.

**Warning signs:**
Engine repeats in a winning position; `nps` unexpectedly low with draw-detection enabled; TT poisoning where a drawn line's score leaks into a non-repeating path.

**Phase to address:** M2.

---

### Pitfall 10: NNUE side-to-move perspective sign error (THE NNUE killer bug)

**What goes wrong:**
The two-perspective NNUE takes **two** feature sets — one from the side-to-move's (STM) perspective, one from the non-STM perspective — concatenates the accumulators in `[STM, non-STM]` order, and outputs a score **from the side-to-move's POV**. The classic bug: building features from a fixed White perspective (or getting the King-square/piece-color mirroring wrong), or concatenating the two halves in the wrong order, or feeding a White-POV score into a negamax search that expects STM-POV. Every one of these produces a net that trains to low loss on labels but plays *terribly* — often actively worse than the handcrafted eval — because the sign/perspective is inconsistent between training labels, the net, and the search.

**Why it happens:**
There are three independent sign conventions that must all agree: (1) how training labels are signed (Stockfish eval is reported White-relative in FEN datasets but STM-relative in others — you must know which), (2) how the net's two input perspectives are built and ordered, (3) how the search consumes the output. A mismatch anywhere is silent — loss still goes down.

**How to avoid:**
Pin the convention **explicitly and test it**: net output = score for the side to move. When building features, the "own" perspective is always the side to move; mirror the board vertically (and swap piece colors) for the STM so "my pieces" always occupy the same feature indices regardless of color — matching `official-stockfish/nnue-pytorch`'s HalfKP/HalfKA perspective construction. Concatenate `[own_accumulator, their_accumulator]`. In the dataloader, normalize every label to STM-POV (if a source is White-relative, flip the sign when it's Black to move). **Golden test:** a symmetric position must evaluate to ~0; a position and its color-mirror-with-STM-flip must give equal scores; feed the net a position where White is up a queen and confirm the score is large-positive when it's White's move and large-negative when it's (illegally, for testing) Black's move. Compare a handful of net evals against Stockfish's own eval sign on the same FENs.

**Warning signs:**
Training loss looks great but engine strength is *below* the handcrafted baseline; engine plays reasonable openings then collapses; symmetric/mirrored positions don't evaluate symmetrically; the deeper it searches with NNUE, the worse the move.

**Phase to address:** M3. **This is a required checklist item (see quality gate).**

---

### Pitfall 11: Eval scale / units mismatch — centipawns vs win-probability sigmoid target

**What goes wrong:**
Training the net to regress raw Stockfish centipawns with MSE (a) lets huge evals (±10000 for mates) dominate the loss and destabilize training, and (b) mismatches how modern NNUE nets are actually trained — against a **win-probability** target via a sigmoid, blending the engine eval with the game result. Also: post-training, the search interprets the net's output in the wrong units, so `score cp` reported to the GUI is nonsense and time/pruning heuristics tuned in "cp" misbehave. And: Stockfish's UCI cp output has been **normalized** since SF12+ (100cp ≈ 50% win prob at LTC), so it is *not* the internal value — mixing normalized cp with internal eval when labeling corrupts the target scale.

**Why it happens:**
"Centipawns" feels like the natural target, but NNUE training uses `sigmoid(eval / scaling)` (Stockfish uses a scaling constant around 361–400) to map eval into [0,1] win space, then trains on a mix of that and the actual game outcome. The units convention has to be consistent across label extraction, loss, and inference.

**How to avoid:**
Decide the target space up front: train on `sigmoid(cp / K)` (win-prob), typically with a loss that interpolates `lambda * sigmoid(engine_eval) + (1-lambda) * game_result`, following `nnue-pytorch`. Store labels as raw internal-consistent cp (or the WDL), pick K to match your data (~360–400 for SF-scaled data — measure it, don't guess). At inference, invert consistently: the net predicts win-prob or scaled-cp; convert to an integer cp for `score cp` output and for search using the *same* K. Clamp/cap mate-ish labels rather than feeding ±10000 into MSE. Document the exact Stockfish command used for labeling (`eval` vs search score, depth, whether output is normalized) because SF's normalized cp ≠ internal eval.

**Warning signs:**
Training loss dominated by a few extreme positions; `score cp` output wildly out of line with Stockfish on the same FEN; net "confident" everywhere (saturated) or "timid" everywhere; strength worse than expected despite low loss.

**Phase to address:** M3.

---

### Pitfall 12: Train/validation data leakage and mislabeled positions

**What goes wrong:**
(a) The same position (or trivial transpositions / same game's adjacent plies) appears in both train and validation, so val loss looks great but doesn't reflect generalization — you can't trust it to decide when to stop or which net is better. (b) Positions labeled at inconsistent Stockfish depth/nodes, or labeled while in check / with a mate score, contaminate the target. (c) Duplicate positions overweight common openings.

**Why it happens:**
Chess datasets are hugely redundant (opening positions recur across millions of games; consecutive plies are near-identical). A random row split leaks. And labeling pipelines are fiddly — easy to label at varying depth or include unsuitable positions.

**How to avoid:**
Split by **game**, not by position (all positions from one game go entirely to train or val), and ideally by opening/time period too. Deduplicate positions by FEN (or Zobrist) before splitting; consider filtering to positions that are "quiet" (side-to-move not in check, best move not a capture) as Stockfish NNUE data pipelines do, so the eval is stable. Label every position with a **fixed** Stockfish depth/nodes and record it. Skip or specially handle in-check and mate-scored positions. Hold out a truly independent test set (different games) for final A/B.

**Warning signs:**
Val loss much lower than expected / suspiciously close to train loss; net that "validates" well but doesn't win more games; identical FENs found in both splits (write a check for this).

**Phase to address:** M3.

---

### Pitfall 13: Quantization mismatch between training and inference (or skipping quantization semantics entirely)

**What goes wrong:**
NNUE gets its speed from int8/int16 integer inference with fixed scaling (feature-transformer activation scaled to 0..127 via ClippedReLU, weights scaled by ~64). If you train float32 with plain ReLU and no awareness of the clamp/scale, then either (a) you never quantize and eat a large `nps` penalty (partly acceptable in pure Python, but you lose the standard NNUE inference path and can't reuse SF-style code), or (b) you quantize naively and the clamped/rounded integer net evaluates differently from the float net you validated — strength silently drops after "shipping".

**Why it happens:**
The clamp (ClippedReLU 0..127), the weight/activation scale factors, and rounding all change the function. Training must use ClippedReLU (clamp 0..1 in float, mapped to 0..127) and keep weights within a range that survives int8 quantization, or quantization-aware assumptions break.

**How to avoid:**
Even for a pure-Python first cut, mirror the `nnue-pytorch` recipe: use ClippedReLU (`clamp(x, 0, 1)`), keep the architecture `(768→N)×2→1` small, and if you plan to quantize, clip weights during training and validate the **quantized** net (not just the float net) on a held-out set and in a mini-gauntlet before declaring a strength gain. If you defer quantization (reasonable while Python-bound), keep the float path but make the eval interface return integer cp so swapping in a quantized net later doesn't change the search contract. Document the scale constants (127 activation, 64 weight) so the future Rust port matches.

**Warning signs:**
Float net and quantized net disagree materially on the same FENs; strength regresses right after adding quantization; activations regularly exceed the clamp range (weights too large for int8).

**Phase to address:** M3 (design the eval interface for it in M1's swappable-eval boundary).

---

### Pitfall 14: MPS-specific traps — float64, silent CPU fallback, and unified-memory OOM

**What goes wrong:**
- **float64:** MPS does not support float64 at all — any `torch.float64` tensor (easy to introduce via NumPy interop, `double()`, or a default-dtype slip) raises `Cannot convert a MPS Tensor to float64` or silently forces a CPU round-trip. Confirmed current limitation on recent PyTorch.
- **Silent CPU fallback:** With `PYTORCH_ENABLE_MPS_FALLBACK=1` set (needed for unimplemented ops), unsupported ops fall back to CPU *silently*, so a "GPU" training run is secretly bottlenecked by CPU<->GPU copies and you just see mysteriously low utilization / slow epochs.
- **Kernel correctness bugs:** MPS has had real silent-wrong-result kernel bugs (e.g. in-place `addcmul_`/`addcdiv_` and RNG ops writing to non-contiguous tensors on macOS < 15). These don't error — they produce wrong numbers, which for a net means "trains but to the wrong thing."
- **Unified-memory OOM:** The 24 GB is shared with macOS and every other app. A batch size that fits on a dedicated 24 GB GPU can OOM here because the OS + browser already hold several GB, and MPS memory pressure can stall or kill the process.

**Why it happens:**
MPS is still maturing; the abstractions hide where compute actually runs, and unified memory means "GPU memory" isn't yours alone.

**How to avoid:**
Set `torch.set_default_dtype(torch.float32)` and assert no tensor is float64 (a startup guard). Pin macOS to a recent version (≥15) and PyTorch ≥2.4 (the PROJECT.md already recommends this) to dodge the known kernel bugs; **validate numerics** by training a tiny net on CPU and on MPS and confirming near-identical loss curves before trusting MPS for the real run. Detect fallback: log which ops fall back (or run a smoke test with fallback disabled to see what breaks) and avoid those ops in the hot path. Size batches conservatively (start small, watch Activity Monitor memory pressure), close other apps for long runs, and checkpoint frequently so an OOM kill doesn't lose the run. Prefer bfloat16/float32 over chasing FP16/AMP — AMP gives little benefit on MPS for these nets (per PROJECT.md).

**Warning signs:**
`float64` dtype errors; GPU utilization low while CPU is pegged during "MPS" training; loss curve differs between CPU and MPS for the identical seed/data (kernel bug); process killed or system beachballs mid-epoch (OOM/memory pressure).

**Phase to address:** M3 (add the float32 guard + CPU-vs-MPS numeric sanity check as the first thing in the training harness).

---

### Pitfall 15: Measuring Elo/strength with too few games, no opening book, or self-play draw bias

**What goes wrong:**
Declaring "NNUE is +80 Elo" from 50 games (the ±95% confidence interval at 50 games is roughly ±120 Elo — larger than most real gains), or running the gauntlet from the start position every game (deterministic engines repeat the same game, and near-equal engines draw constantly, so you learn nothing), or A/B-ing two versions with different search settings so you can't attribute the difference to the net.

**Why it happens:**
Match variance is huge and unintuitive; determinism + equal strength collapses game diversity; and it's tempting to change search + eval together.

**How to avoid:**
Use a **fixed, varied opening book** (e.g. an `.epd`/`.pgn` of balanced 4–8 ply openings, each played from both colors) so games diverge and aren't repeats. Run **≥1000 games** for a gauntlet result you'll act on (PROJECT.md already commits to this) and report the SPRT/LOS or the Elo confidence interval, not a bare win count — use Cute Chess's built-in output or the standard `bayeselo`/`ordo` tooling. **Change one thing at a time:** hold search identical, swap only the eval, to isolate the net's contribution. Fix time control (or nodes-per-move for determinism-free comparison) and hardware/thread count across both sides. Beware draw bias: at near-equal strength, use the "wins − losses" signal with proper CIs, not draw-inflated "score%".

**Warning signs:**
Elo claims from < a few hundred games; every gauntlet game is the same moves; a "gain" that vanishes on a rerun; comparisons where both search and eval changed.

**Phase to address:** Set up in M2 (gauntlet harness + opening book), used decisively in M3 (NNUE vs handcrafted A/B). This is the measurement backbone for the whole project.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Recompute NNUE accumulator from scratch each leaf (no incremental update) | Simpler eval code | Loses NNUE's core speed advantage; misleads the future Rust port about the real hot path | OK for the first correct Python net; note it clearly as the #1 port-time optimization |
| Use `python-chess`'s `board.is_repetition()`/`can_claim_draw()` in the search hot loop | Correct with zero effort | Tanks `nps`, caps search depth further | Only at the root; never per-node |
| Regress raw centipawns with MSE instead of sigmoid-WDL target | Fastest to code | Unstable training, wrong units, doesn't match SF pipeline; likely a redo | Never for the shipped net; OK for a 10-minute "does the pipeline run" smoke test |
| Skip the TT entirely to "keep search simple" | Fewer bugs early | Search too shallow to be useful; move ordering benefit lost | Only for the very first depth-limited spike, then add it in M2 |
| Single-threaded UCI loop (search blocks reader) | Trivial to write | Can't honor `stop`, loses on time in real matches | Never past the throwaway REPL stage — build threaded from M1 |
| Defer quantization (float-only eval) | Avoids quantization bugs now | `nps` penalty; net validated in float ≠ eventual int8 net | Acceptable this milestone (Python-bound anyway) **if** the eval interface returns integer cp and scale constants are documented |
| Hardcode piece values / no opening book in gauntlet | Fewer moving parts | Unmeasurable/biased strength results | Never for a result you'll act on |

---

## Integration Gotchas

Common mistakes when connecting to external services/tools.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `python-chess` movegen | Hand-rolling UCI move parsing (promotions/castling) | Use `board.push_uci()` / `Move.from_uci()`; let the library own legality |
| `python-chess` draw detection | Per-node `can_claim_draw()` in search | Own Zobrist/halfmove stack in search; library call only at root |
| Cute Chess / Arena (UCI arbiter) | Block-buffered stdout; ignoring `stop`; no `bestmove` on edge cases | `flush=True`/`-u`; threaded search polling a stop flag; exactly one `bestmove` per `go` |
| Stockfish (labeling) | Mixing normalized UCI cp with internal eval; varying depth per position | Fix depth/nodes; record the exact command; know normalized-cp ≠ internal value (SF12+) |
| Stockfish/Lc0 (gauntlet opponent) | Comparing across different TC/hardware/threads; no shared opening book | Identical TC, threads, book for both sides; anchor to one consistent opponent pool |
| lichess-bot | Assuming engine handles `go` params it never implemented (`ponder`, `nodes`) | Explicitly parse/ignore unsupported params without hanging; test the exact `go` strings it sends |
| PyTorch MPS | NumPy interop introducing float64; assuming ops run on GPU | float32 default + guard; verify op placement; CPU-vs-MPS numeric check |

---

## Performance Traps

Patterns that work at small scale but fail as depth/data grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Pure-Python per-node overhead (object churn, `deepcopy` of board) | `nps` in low thousands; depth stuck at 4–6 | Use `push`/`pop` (make/unmake), not board copies; minimize per-node allocations; avoid `deepcopy` | Immediately — this *is* the Python ceiling; don't fight it past reasonable hygiene |
| Calling `time.monotonic()` / `board.legal_moves` list-materialization every node | `nps` lower than expected | Check clock every ~2–4k nodes; iterate legal moves lazily; cache in-check status | At useful depths in tactical positions |
| Quiescence with quiet moves or uncapped checks | Node count explodes 10–100× | Captures/promotions only + delta pruning + qsearch depth cap | In sharp/tactical positions |
| Premature micro-optimization of Python search instead of algorithmic gains | Weeks lost; still slow | Prioritize move ordering (hash move, MVV-LVA, killers), TT, pruning — algorithmic depth beats constant-factor Python tweaks; defer raw speed to the Rust port | Ongoing temptation — the port is the real speed lever (out of scope this milestone) |
| Recompute-from-scratch NNUE accumulator per leaf | `nps` halves again on top of Python cost | Accept for now; document incremental update as port priority | Once NNUE is the leaf eval (M3) |
| MPS silent CPU fallback in training loop | Slow epochs, low GPU util | Detect/avoid fallback ops; keep the hot path on supported ops | Large-batch/long training runs |
| Loading whole labeled dataset into RAM | OOM as data grows (shared 24 GB) | Stream/shard from disk; memory-map; cap batch size | When training set exceeds a few GB |

---

## Security Mistakes

Domain-specific issues (this is a local tool, so scope is narrow — but not zero).

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trusting arbitrary FEN/UCI input from stdin without validation | Crash / undefined behavior on malformed `position fen ...`; DoS via pathological input | Validate FEN via `python-chess`; on parse failure, log and skip rather than crash; never `eval()`/`exec()` input |
| Loading model checkpoints via `torch.load` (pickle) from untrusted sources | Arbitrary code execution (pickle deserialization) | Only load your own checkpoints; prefer `weights_only=True` / `safetensors` for any shared/downloaded net |
| Ingesting downloaded PGN/EPD training data unsanitized | Malformed records crash the pipeline; path traversal if filenames are trusted | Validate/parse defensively; treat dataset files as untrusted input; sanitize any file paths |
| lichess-bot token / API key in source | Credential leak | Env var / secret store; never commit tokens |

---

## UX Pitfalls

"User" here = the GUI/arbiter and the human running gauntlets.

| Pitfall | Impact | Better Approach |
|---------|--------|-----------------|
| No/incorrect `info` output during search | GUI shows no thinking; hard to debug; looks frozen | Emit `info depth D score cp X nodes N nps M time T pv ...` each iteration; correct `score mate N` for mates |
| `pv` that doesn't match the reported score/bestmove | Confuses analysis; signals a TT/search bug | Extract PV from the TT (or a triangular PV table) consistent with the search result; test PV[0] == bestmove |
| Slow/absent response to `isready` | Arbiter thinks engine died | Answer `readyok` immediately from the reader thread, never gated behind search |
| Reporting `nps`/`nodes` inconsistently or omitting them | Can't gauge search health | Track a global node counter; report every iteration and at bestmove |
| Not implementing `ucinewgame` (stale TT across games) | Cross-game contamination, subtle strength loss | Clear/age the TT on `ucinewgame` |

---

## "Looks Done But Isn't" Checklist

- [ ] **UCI loop:** Handles `stop` mid-search and returns a `bestmove` — verify with a piped `position/go/stop` script, not just interactive use.
- [ ] **UCI loop:** stdout flushed on every line — verify by driving the engine through a pipe/Cute Chess, not a TTY.
- [ ] **`go`:** *Every* variant (`movetime`, `depth`, `nodes`, `infinite`, `wtime/btime/inc`, and bare `go`) yields exactly one `bestmove`, including in mate/stalemate/zero-move positions.
- [ ] **Time management:** Hard limit is checked *inside* the node loop, not only between iterations — verify no time forfeits over a 100-game blitz gauntlet.
- [ ] **TT:** Mate scores adjusted by ply on store *and* probe — verify with mate-in-2/3 suites that `score mate N` is stable across depths.
- [ ] **TT:** Bound flags correct — verify fixed-depth search is reproducible and PV[0] == bestmove.
- [ ] **Search:** Draw detection (3-fold/50-move/insufficient material) active in search — verify engine doesn't repeat in a won position.
- [ ] **Search:** Checkmate = `-MATE+ply`, stalemate = 0, negamax sign correct — verify deeper search never plays *worse*.
- [ ] **NNUE:** STM perspective + concatenation order correct — verify symmetric positions ≈ 0 and mirror-with-STM-flip gives equal scores.
- [ ] **NNUE:** Labels normalized to STM-POV and to a consistent unit/scale — verify a few net evals match Stockfish's sign and rough magnitude.
- [ ] **NNUE:** Train/val split by game (not position) with FEN dedup — verify no FEN appears in both splits.
- [ ] **NNUE:** The *quantized/deployed* net (not just the float net) is A/B-tested — verify float and deployed net agree on sample FENs.
- [ ] **MPS:** No float64 anywhere; CPU-vs-MPS loss curves match on a tiny net — verify before the real training run.
- [ ] **Eval boundary:** Swapping handcrafted → NNUE changes *only* the eval, not the search — verify by diffing search config across the A/B.
- [ ] **Measurement:** Gauntlet uses a fixed opening book and ≥1000 games with reported CI/SPRT — verify before claiming any Elo gain.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| TT mate-score bug | LOW | Add ply adjustment on store/probe; re-run mate suite; no data loss |
| TT bound-flag bug | MEDIUM | Audit store sites for EXACT/LOWER/UPPER; add fixed-depth reproducibility test; may require re-tuning pruning |
| Search blocks on `stop` | MEDIUM | Refactor to reader-thread + search-thread with a stop flag; touches the loop core — cheaper if done in M1 |
| NNUE perspective/sign error | MEDIUM–HIGH | Fix feature construction + label sign; **retrain** (labels may need re-signing); re-run golden symmetry tests + mini-gauntlet |
| Data leakage (position-split) | HIGH | Re-split by game, dedup FENs, **retrain**, and distrust all prior val-based decisions |
| Quantization mismatch | MEDIUM | Retrain with ClippedReLU + weight clipping or fix scale constants; validate the quantized net directly |
| MPS numeric/kernel bug | MEDIUM | Upgrade macOS/PyTorch; re-validate CPU vs MPS; possibly retrain if a run was silently corrupted |
| Elo claim from too few games / no book | LOW | Re-run the gauntlet properly (book + ≥1000 games); recompute CI — only wasted time, no code change |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Search blocks stdin / `stop` ignored | M1 | Piped `position/go/stop` script yields prompt `bestmove` |
| No stdout flush / missing `bestmove` | M1 | Driven via pipe & Cute Chess; exactly one `bestmove` per `go` |
| `position ... moves` state corruption | M1 | Resulting FEN diffed vs GUI; legality assertions pass |
| `ucinewgame` doesn't reset TT | M1 | TT cleared/aged between games |
| Time-loss forfeits | M2 (parsed in M1) | Zero time losses over a 100-game blitz gauntlet |
| TT mate-score not ply-adjusted | M2 | Mate-in-2/3 suite; stable `score mate N` across depths |
| TT bound flags wrong | M2 | Fixed-depth reproducibility; PV[0] == bestmove |
| Quiescence explosion | M2 | Bounded node counts in tactical suite; qsearch = captures+promos only |
| Checkmate/stalemate/sign errors | M2 | Terminal-node unit tests; deeper search never worsens play |
| Repetition/50-move draws | M2 | Engine doesn't repeat in won positions; cheap in-search detection |
| Gauntlet harness + opening book | M2 | Book-driven, ≥1000-game runs with CI/SPRT output |
| NNUE STM perspective/sign | M3 | Symmetry golden tests; sign matches Stockfish on sample FENs |
| Eval scale/units (sigmoid-WDL) | M3 | `score cp` aligns with Stockfish; stable training loss |
| Train/val data leakage | M3 | No shared FENs across splits; split-by-game enforced |
| Quantization mismatch | M3 (interface in M1) | Deployed net == float net on samples; quantized net A/B-tested |
| MPS float64 / fallback / OOM | M3 | float32 guard; CPU-vs-MPS loss parity; conservative batch size |
| Swappable-eval contract broken | M1 boundary, exercised M3 | NNUE swaps in changing only eval; search config identical in A/B |
| Elo measured with too few games | M2 harness, decisive in M3 | ≥1000 games, fixed book, reported CI; result survives a rerun |

---

## Sources

- `official-stockfish/nnue-pytorch` — `docs/nnue.md` (definitive NNUE write-up: two-perspective/STM feature construction, ClippedReLU, quantization scales 127/64, sigmoid-WDL training target) — https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md and https://official-stockfish.github.io/docs/nnue-pytorch-wiki/docs/nnue.html — **HIGH**
- Stockfish "Normalize evaluation" commit + wiki (normalized UCI cp ≠ internal value since SF12+; 100cp ≈ 50% win at LTC; WDL scaling constant ~360–400) — https://github.com/official-stockfish/Stockfish/commit/ad2aa8c06f438de8b8bb7b7c8726430e3f2a5685 and https://official-stockfish.github.io/docs/stockfish-wiki/Useful-data.html — **HIGH**
- PyTorch MPS issue tracker / forums (no float64 on MPS; silent CPU fallback with `PYTORCH_ENABLE_MPS_FALLBACK=1`; non-contiguous in-place/RNG kernel bugs on macOS < 15) — https://github.com/pytorch/pytorch/issues/177819 and https://discuss.pytorch.org/t/apple-m1-silicon-typeerror-cannot-convert-a-mps-tensor-to-float64-dtype/164655 — **HIGH** (MEDIUM on exact macOS-version thresholds — verify against your installed macOS/PyTorch)
- UCI protocol conventions and common-engine bug patterns (Chess Programming Wiki: transposition table, mate scores, quiescence, time management, negamax) — engine-development community consensus — **HIGH**
- Match/Elo variance and testing methodology (SPRT/LOS, opening books, Cute Chess) — Stockfish fishtest / TCEC community practice — **HIGH**
- Project constraints and known caveats — `.planning/PROJECT.md` — **HIGH**

---
*Pitfalls research for: UCI chess engine + supervised NNUE (Python / PyTorch MPS on M4)*
*Researched: 2026-07-05*
