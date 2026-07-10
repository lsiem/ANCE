---
status: issues_found
phase: 02-core-alpha-beta-search
depth: standard
files_reviewed: 20
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
---

# Phase 02 Code Review

## Scope

Reviewed the 20 existing Python source and test files named by
`key-files.created` and `key-files.modified` across Plans 02-01 through
02-10. Planning files and the generated evidence JSON were used only as
context. Commit `c915011` was reviewed in full and `2303836` was checked
against the collector output and the Plan 02-07 through 02-09 contracts.

Focused verification:

- `37 passed, 2 deselected` across the collector, deadline, telemetry,
  generation, depth-match, and gauntlet fast tests.
- `python -m compileall -q ance tests` passed.

## Findings

### Critical

#### C1. A timed-out pytest command can leave engine descendants running beyond the advertised hard wall

`_run_command` uses `subprocess.run(..., timeout=...)`, which kills only the
direct pytest process on timeout. Several included tests create engine
subprocesses. Those descendants share the collector session but are not
necessarily terminated when pytest is killed. The child then writes a failure
artifact and exits; when the supervisor sees that artifact, it returns directly
without terminating the session process group. The watchdog is disabled in the
supervisor's `finally`, so orphaned engines can survive the collector and exceed
the claimed process bound.

References:

- `ance/tools/phase2_deterministic_evidence.py:157-172`
- `ance/tools/phase2_deterministic_evidence.py:747-756`
- `ance/tools/phase2_deterministic_evidence.py:772-775`

Action: run each pytest command in its own process group and terminate/reap that
group on timeout, or make every abnormal collector-child exit trigger
termination and reaping of the collector session before returning. Add a real
descendant-process regression rather than only a fake direct-child test.

### Warnings

#### W1. A committed passed artifact suppresses all future evidence collection without proving code identity

When both artifacts exist, `main` accepts a weak terminal validation and returns
before resolving the current commit or running any test. The committed artifact
records `c915011`, while the current HEAD is later; the current Python tree
happens to be unchanged, but a future source change would still reuse the old
pass indefinitely. `validate_terminal_artifacts` checks contract/status/timing
and a summary status string, not the reviewed tree, test inventory, command
records, or artifact-to-summary identity.

References:

- `ance/tools/phase2_deterministic_evidence.py:519-534`
- `ance/tools/phase2_deterministic_evidence.py:682-688`
- `tests/test_phase2_deterministic_evidence.py:107-129`

Action: bind evidence to a deterministic hash of the reviewed source/test tree
and collector configuration, and only reuse artifacts when that identity
matches. Otherwise rerun or require an explicit `--reuse` option.

#### W2. Quiescence descendants bypass repetition and rule-draw detection

`negamax` checks `_is_draw_position` and pushes a path key only before entering
quiescence. Recursive quiescence calls do neither. A capture/check sequence
inside qsearch can therefore reach a game-history repetition, search-path
repetition, fifty-move draw, or insufficient-material draw and receive a static
or tactical score instead of zero. Plan 02-07's repetition fix and its tests
cover main-search nodes but not qsearch descendants.

References:

- `ance/search/negamax.py:122-183`
- `ance/search/negamax.py:186-233`
- `tests/test_iterative_deepening.py:34-69`

Action: apply draw detection and balanced path-key tracking at every qsearch
node, then add a depth-zero regression whose qsearch continuation repeats a
historical/path position.

#### W3. The qsearch depth cap evaluates positions while the side to move is still in check

The `qdepth >= MAX_QDEPTH` return occurs before the in-check branch. At the cap,
an unresolved check is treated as a normal static position; mate or a forced
evasion can consequently be scored as evaluator centipawns. This contradicts
the established “in-check -> evasions only” contract.

References:

- `ance/search/negamax.py:129-140`
- `tests/test_quiescence.py:62-79`

Action: handle terminal/check nodes before applying the quiet qdepth cap, or
continue check evasions under a separately bounded policy. Add a regression
that reaches the cap while in check.

#### W4. An unexpected search exception violates UCI's one-bestmove-per-go contract

`_run_search` has cleanup in `finally` but no exception handler. If search,
evaluation, or an info callback raises, execution never reaches the
generation-gated `send_bestmove`; the daemon thread only prints a traceback and
the GUI can wait indefinitely. Current generation tests cover cancellation and
staleness, not worker failure.

References:

- `ance/uci/loop.py:104-148`
- `tests/test_uci_generation.py:34-122`
- `tests/test_go_bestmove.py:164-205`

Action: catch expected and unexpected worker failures, log them on stderr, and
emit exactly one generation-gated fallback `bestmove` (legal fallback or
`(none)` according to policy). Add a deterministic raising-search regression.

#### W5. The random opponent is re-seeded on every move, so it is not a uniform random game trajectory

`play_game` constructs `RandomMover(seed)` inside every opponent turn. Each turn
therefore consumes the first PRNG sample from a fresh generator instead of a
sequence from one seeded generator. Runs remain deterministic, but the module's
“uniformly-random legal-move opponent” and future statistical-gauntlet premise
are not implemented as stated. Plan 02-10 correctly defers statistical claims,
so the committed deterministic evidence is not invalidated.

References:

- `ance/tools/random_mover_gauntlet.py:98-105`
- `ance/tools/random_mover_gauntlet.py:142-160`
- `tests/test_random_mover_gauntlet.py:26-42`

Action: instantiate one `RandomMover` before the game loop and reuse it for all
opponent turns. Add a test proving successive choices consume successive RNG
state while replaying the same seed remains deterministic.

## Plan Alignment

The main Plan 02-07 deadline/telemetry fixes, Plan 02-08 generation isolation,
and Plan 02-09 deeper-side result normalization are present and their focused
tests pass. Commit `2303836` accurately labels its two-game runtime sample as
non-statistical calibration. The issues above concern qsearch completeness,
failure paths, and whether the new collector can safely and durably substantiate
that evidence.
