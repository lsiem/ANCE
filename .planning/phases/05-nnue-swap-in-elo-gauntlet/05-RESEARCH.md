# Phase 5: NNUE Swap-In & Elo Gauntlet — Research

**Researched:** 2026-07-18  
**Domain:** numpy NNUE inference behind the Evaluator seam, torch↔numpy parity, fixed-depth self-play measurement  
**Confidence:** HIGH

## Summary

Phase 5 is the milestone payoff: wire a zero-torch `NnueEval` behind the existing `Evaluator` Protocol, load the Phase 4 approved `net.safetensors` (790 KB, `768x2-256-1` / `board768`), prove correctness with exact integer parity and perspective goldens, then run a ≥1000-game gauntlet where only `ANCE_EVAL` (and optionally `ANCE_NNUE_PATH`) differs between builds.

The codebase is ready for this slice. The seam (`ance/eval/base.py`), UCI entry (`ance/uci/loop.py`), weight contract (`nnue_format/*`), feature encoder oracle (`training/data/features.py`), torch forward reference (`training/model.py`), and gauntlet harness (`ance/tools/gauntlet.py`) all exist. Phase 4 verification explicitly deferred engine-side load to this phase; the approved weights at `.planning/phases/04-offline-nnue-training-pipeline/run-output/net.safetensors` are the canonical source to copy per D-07.

Two implementation gaps block TOOL-04 as-is and must appear in the plan:

1. **Gauntlet is clock-only today.** `play_gauntlet_game()` always passes `chess.engine.Limit(white_clock=…, black_clock=…)` — no `--depth` mode. D-11 requires fixed `go depth N` on both sides; extend the harness to use `Limit(depth=N)` (python-chess supports this [CITED: python-chess engine docs]) and record the mode in checkpoint parameters.
2. **Gauntlet does not inject per-engine env vars.** D-04/D-01 require identical argv with `ANCE_EVAL` differing. `SimpleEngine.popen_uci(..., env=merged_env)` via `**popen_args` is the standard injection surface [VERIFIED: codebase — `tests/test_go_bestmove.py` already passes custom `env=` to subprocess; `popen_uci` accepts `**popen_args` per signature probe].

Local benchmark on this machine (handcrafted, startpos, TT warm-ish): depth 2 ≈ 0.05 s, depth 3 ≈ 0.33 s, depth 4 ≈ 2.13 s per `search_root` call. At ~40 half-moves/game × 1000 games ≈ 40k searches, depth 3 projects ~4–8 h wall-clock (NNUE adds leaf matmul cost); depth 4 projects ~20+ h. **Recommend depth 3** for the acceptance run unless a Wave 0 benchmark shows otherwise.

**Primary recommendation:** Implement `ance/eval/nnue/` (encoder + `NnueEval` + shared `cp_from_nnue_output`), wire `ANCE_EVAL`/`ANCE_NNUE_PATH` in `loop.py` mirroring `ance/debug.py`, extend gauntlet with `--depth` + per-`EngineSpec` env, copy approved net to `ance/eval/nnue/net.safetensors`, then gate on parity/golden pytest before the slow ≥1000-game evidence run.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Eval switch / two-build wiring
- **D-01:** Select evaluator via env var `ANCE_EVAL=handcrafted|nnue` (not CLI flags or UCI `setoption` for this phase). Matches existing `ANCE_DEBUG` pattern and works with cutechess `arg=` / python-chess arbiter alike.
- **D-02:** Default when unset is **handcrafted**. NNUE only when `ANCE_EVAL=nnue`. Keeps GUI/casual play on the known-good eval until TOOL-04 proves a gain.
- **D-03:** Unknown / invalid `ANCE_EVAL` → **fail fast** (non-zero exit, stderr lists allowed values). No silent fallback.
- **D-04:** Both gauntlet builds use the **same** `python -m ance` argv; only `ANCE_EVAL` (and optionally `ANCE_NNUE_PATH`) differs. Diff-verify search config by comparing everything except the eval-selection env.

#### Weights path contract
- **D-05:** Load order: `ANCE_NNUE_PATH` if set, else a **baked-in package default** under `ance/` (planner picks exact path, e.g. `ance/eval/nnue/net.safetensors`).
- **D-06:** Missing file or `nnue_format` validation failure when `ANCE_EVAL=nnue` → **fail fast at startup**. No silent handcrafted fallback.
- **D-07:** Copy the Phase 4 approved `.planning/phases/04-offline-nnue-training-pipeline/run-output/net.safetensors` into the package path and **track it in git** (~790 KB).
- **D-08:** Load-time checks are **strict**: `arch_id`, `feature_set`, and tensor shapes must match `nnue_format.schema` constants (`768x2-256-1`, `board768`).

#### Elo gauntlet protocol (TOOL-04)
- **D-09:** Runner policy = Phase 3 **D-15**: prefer `cutechess-cli` when on PATH, else python-chess external arbiter. Do not block TOOL-04 on cutechess install. Evidence must record which runner was used. (Amends ROADMAP's cutechess-only wording for this machine.)
- **D-10:** Fixed **≥1000 games** (no SPRT early-stop for the acceptance run). Report Elo + 95% CI; resume via existing gauntlet checkpoints.
- **D-11:** **Fixed depth** both sides (`go depth N`); planner/research picks N that fits a bounded overnight wall-clock. Not blitz clocks for the Elo proof.
- **D-12:** Pass criterion: Elo **point estimate > 0** and **95% CI lower bound > 0**.

#### Parity & golden acceptance bar
- **D-13:** Torch ↔ numpy parity: **exact** integer cp after the shared float→int conversion on held-out FENs.
- **D-14:** Symmetric positions: eval **exactly 0** (tempo/startpos conventions as already established for handcrafted tests — research confirms which FENs).
- **D-15:** Color-mirror with STM flip: **exact equality** in integer cp.
- **D-16:** Stockfish comparison: **sign agreement** on a small fixed suite of clearly won/lost positions — not strict magnitude correlation to SF.

### Claude's Discretion
- Exact package-relative path for the baked-in net under `ance/`.
- Concrete held-out FEN suite size and contents for parity / goldens / SF-sign.
- Fixed search depth `N` and opening-book size for the overnight ≥1000-game run.
- Elo reporting formula details (BayesElo / logistic / simple score→Elo) as long as D-12's CI lower-bound > 0 gate is met.
- How the diff-verify of "identical search config" is automated in tests/CI.

### Deferred Ideas (OUT OF SCOPE)
None raised during discussion beyond already-scoped-out items (incremental accumulator, big nets, GUI, compiled port).

#### Reviewed Todos (not folded)
- `2026-07-07-tool-02-depth-4-gauntlet-deferred.md` — search/pruning backlog, not NNUE Elo.
- `2026-07-07-v1_1-gui-local-web-app.md` — v1.1 milestone.
- `2026-07-08-phase2-encroissant-validation.md` — already past Phase 2.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **EVAL-03** | A `(768→N)×2→1` NNUE evaluator implements the same interface, loading trained weights | `NnueEval.evaluate(pos)->int` using `nnue_format.io.load_net`, numpy matmul mirroring `training/model.py`, feature encoder mirroring `training/data/features.py`; wired via `ANCE_EVAL` in `loop.py` |
| **TOOL-04** | NNUE build shows measurable Elo gain over handcrafted across ≥1000-game gauntlet with error bars | Extend `gauntlet.py` for fixed-depth + env injection; reuse Wilson CI + logistic Elo; 31-opening book already exists; depth 3 recommended; arbiter runner (cutechess absent on this machine) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.12+, native arm64; `python-chess`, PyTorch (training/tests only), NumPy for inference.
- Evaluation must remain a swappable module — search must not import concrete evaluators (`tests/test_eval_seam.py` structural proof).
- `ance/` must never import `training/` (enforced by `tests/training/test_no_torch_leakage.py`).
- Pure-Python search ceiling accepted; full NNUE recompute (no incremental accumulator) this phase.
- GSD workflow: phase work goes through `/gsd-execute-phase` (informational for planner).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| NNUE forward pass (numpy) | Engine eval module (`ance/eval/nnue/`) | Shared contract (`nnue_format/io.py`) | Inference lives in engine; weights validated at load boundary |
| Feature encoding (768 board768) | Engine eval module (duplicate of training encoder) | Training encoder as test oracle only | Keeps `ance/` free of `training/` imports |
| Evaluator selection | UCI loop startup (`ance/uci/loop.py`) | Env vars read once at import/init | Matches D-01/D-02; no `setoption` this phase |
| Weight file on disk | Package data under `ance/eval/nnue/` | `ANCE_NNUE_PATH` override | D-05/D-07 git-tracked default |
| Torch↔numpy parity oracle | Test layer (`tests/` with `@pytest.mark.torch`) | `training/model.py` forward | D-13; torch never in `ance/` |
| Perspective / SF goldens | Test layer | Stockfish subprocess for sign suite | D-14–D-16 |
| Fixed-depth gauntlet | Tooling (`ance/tools/gauntlet.py`) | External arbiter subprocess | TOOL-04 measurement backbone |
| Elo + CI reporting | Gauntlet aggregate + evidence JSON | — | Reuses Phase 3 Wilson helper |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **NumPy** | 2.5.1 (venv) [VERIFIED: pip show] | NNUE matmul + ClippedReLU in `NnueEval` | Already project stack; zero-torch inference |
| **safetensors** | 0.8.0 [VERIFIED: pip show] | Load `net.safetensors` via `nnue_format.io` | Phase 4 contract; no torch in loader |
| **chess** (python-chess) | 1.11.2 [VERIFIED: pip show] | Board state, gauntlet arbiter, SF driver | Established since Phase 1 |
| **PyTorch** | 2.13.0 (venv) [VERIFIED: pip show] | Parity oracle in tests only | Phase 4 training reference |
| **pytest** | 9.1.1 [VERIFIED: pip show] | Parity, goldens, gauntlet contracts | Project test runner |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Stockfish** | `/opt/homebrew/bin/stockfish` [VERIFIED: which] | Sign-agreement oracle (D-16) | Golden tests only; skip if absent |
| **nnue_format** | in-repo | Schema + `load_net` validation | Every NNUE startup when `ANCE_EVAL=nnue` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Duplicate encoder in `ance/eval/nnue/features.py` | Move encoder to `nnue_format/features.py` | Cleaner single source, but expands Phase 4 contract scope; duplicate + cross-test is lower risk this phase |
| Logistic Elo from Wilson score rate | BayesElo / cutechess Elo | BayesElo needs extra tooling; logistic + existing Wilson satisfies D-12 |
| cutechess-cli | python-chess arbiter | cutechess absent on this machine (D-09); arbiter already proven in Phase 3 |

**Installation:** No new packages required for Phase 5. Existing venv dependencies suffice.

**Version verification:** All versions confirmed via `.venv/bin/pip show` on 2026-07-18.

## Package Legitimacy Audit

> Phase 5 adds **no new PyPI packages**. Audit covers dependencies touched by new code.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| numpy | PyPI | mature | — | github.com/numpy/numpy | OK (pre-existing) | Approved |
| safetensors | PyPI | mature | — | github.com/huggingface/safetensors | OK (pre-existing) | Approved |
| chess | PyPI | mature | — | github.com/niklasf/python-chess | OK (pre-existing) | Approved |
| pytest | PyPI | mature | — | github.com/pytest-dev/pytest | OK (pre-existing) | Approved |

**Packages removed due to SLOP verdict:** none  
**Packages flagged as suspicious [SUS]:** none (gsd-tools seam returned SUS for all PyPI packages due to missing download metadata in registry API — not actionable for this pre-pinned stack)

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Gauntlet / GUI / pytest subprocess                                     │
│  env: ANCE_EVAL=handcrafted|nnue  (+ optional ANCE_NNUE_PATH)           │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ python -m ance  (argv identical, D-04)
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ance/uci/loop.py                                                       │
│  resolve_evaluator() at startup ──fail fast──► stderr + exit(1)       │
│  module-level `evaluator: Evaluator`                                     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ evaluate(pos) each leaf
                                ▼
┌──────────────────────────┐    ┌──────────────────────────────────────────┐
│ HandcraftedEval          │    │ NnueEval                                  │
│ (default, D-02)          │    │ load_net(path) → numpy weights            │
│                          │    │ encode(board) → stm/opp (768,)            │
│                          │    │ ft → ClippedReLU → concat → out → int cp  │
└──────────────────────────┘    └───────────────┬──────────────────────────┘
                                                │
                    ┌───────────────────────────┴──────────────────────────┐
                    │ nnue_format/io.py (zero torch)                         │
                    │ validates arch_id, feature_set, EXPECTED_SHAPES        │
                    └───────────────────────────┬──────────────────────────┘
                                                │
                    ┌───────────────────────────▼──────────────────────────┐
                    │ net.safetensors (git-tracked default, D-07)            │
                    └────────────────────────────────────────────────────────┘

Parallel test oracle (tests/ only):
  training.model.NNUE(torch) ──parity──► NnueEval(numpy)  [D-13]
  training.data.features.encode_position ──bit-equal──► ance/eval/nnue/features
```

### Recommended Project Structure

```
ance/eval/nnue/
├── __init__.py          # export NnueEval
├── features.py          # 768-index board768 encoder (mirror training/data/features.py)
├── inference.py         # numpy forward + cp_from_nnue_output() shared with tests
├── eval.py              # NnueEval(Evaluator)
└── net.safetensors      # copied from Phase 4 run-output (D-07, ~790 KB)

ance/uci/loop.py         # ANCE_EVAL / ANCE_NNUE_PATH wiring
ance/tools/gauntlet.py   # --depth, EngineSpec.env, Elo report extension

tests/
├── test_nnue_eval.py           # parity, goldens, env fail-fast
├── test_nnue_gauntlet_depth.py # harness depth mode + env injection
└── test_phase5_elo_evidence.py # @pytest.mark.slow ≥1000-game gate
```

### Pattern 1: Env-var eval factory (mirror `ance/debug.py`)

**What:** Read `ANCE_EVAL` once at module init; invalid values → `sys.exit(1)` with allowed list on stderr.  
**When to use:** D-01–D-03; same lifecycle as `ANCE_DEBUG` boolean.  
**Example:**

```python
# Pattern source: ance/debug.py + planned loop.py wiring
import os, sys
from pathlib import Path

_ALLOWED = frozenset({"handcrafted", "nnue"})

def resolve_evaluator():
    mode = os.environ.get("ANCE_EVAL", "handcrafted")
    if mode not in _ALLOWED:
        print(
            f"error: invalid ANCE_EVAL={mode!r}; allowed: {sorted(_ALLOWED)}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if mode == "nnue":
        from ance.eval.nnue.eval import NnueEval
        return NnueEval()  # loads weights; may raise → fail fast (D-06)
    from ance.eval.handcrafted import HandcraftedEval
    return HandcraftedEval()
```

### Pattern 2: NumPy NNUE forward (mirror `training/model.py` + transposed export)

**What:** Full recompute per `evaluate()` call; matmul uses **on-disk transposed** weights from `nnue_format` (see `schema.py` docstring).  
**When to use:** Every leaf evaluation; no incremental accumulator (explicitly out of scope).  
**Example:**

```python
# Weights: ft.weight (768,256), out.weight (512,1) — already transposed at export
def forward_cp_float(stm: np.ndarray, opp: np.ndarray, w: dict[str, np.ndarray]) -> float:
    stm_h = np.clip(stm @ w["ft.weight"] + w["ft.bias"], 0.0, 1.0)
    opp_h = np.clip(opp @ w["ft.weight"] + w["ft.bias"], 0.0, 1.0)
    combined = np.concatenate([stm_h, opp_h])  # (512,)
    return float(combined @ w["out.weight"] + w["out.bias"])  # scalar

def cp_from_nnue_output(raw: float) -> int:
    """Shared float→int conversion for D-13 parity (use round-to-nearest)."""
    return int(round(raw))
```

### Pattern 3: Gauntlet env injection + fixed depth

**What:** Extend `EngineSpec` with optional `env: dict[str, str]` merged over `os.environ`; add `--depth N` that uses `chess.engine.Limit(depth=N)` instead of clock limits.  
**When to use:** TOOL-04 acceptance run (D-11); two specs same argv, env differs only on `ANCE_EVAL`.  
**Example:**

```python
@dataclass(frozen=True)
class EngineSpec:
    name: str
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)

# In run_gauntlet:
base_env = os.environ.copy()
engine_a = chess.engine.SimpleEngine.popen_uci(
    spec_a.argv, env={**base_env, **spec_a.env}
)
# Fixed depth move:
limit = chess.engine.Limit(depth=search_depth)  # D-11
play_result = engine.play(board, limit)
```

### Pattern 4: Structural search-config diff (D-04)

**What:** Automated proof that eval swap does not alter search modules.  
**When to use:** CI gate before slow gauntlet.  
**Example:**

```python
def test_search_modules_unaffected_by_eval_env():
    negamax_src = Path("ance/search/negamax.py").read_text()
    assert "HandcraftedEval" not in negamax_src
    assert "NnueEval" not in negamax_src
    # Optional: hash constants in search/types.py + transposition + ordering unchanged
```

### Anti-Patterns to Avoid

- **Importing `training/` from `ance/`:** Breaks Phase 4 boundary; use tests-only torch imports.
- **Silent fallback to handcrafted when NNUE load fails:** Violates D-06.
- **Using clock TC for TOOL-04 acceptance:** Violates D-11; Phase 3 blitz evidence is not interchangeable.
- **Transposing weights at inference:** Export already transposed; double-transpose breaks parity.
- **startpos tempo golden for NNUE symmetric=0:** Handcrafted uses `TEMPO_BONUS=10` at startpos (`test_startpos_evaluates_to_exact_tempo_bonus`); NNUE has no tempo term — use king-only symmetric FENs for D-14.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Safetensors parsing | Custom binary reader | `nnue_format.io.load_net` | Schema validation, shape checks, Phase 4 provenance |
| NNUE architecture | New layer shapes | Match `training/model.py` exactly | Parity and Elo depend on identical graph |
| Feature indexing | Ad-hoc square loops | Copy `training/data/features.py` verbatim | Off-by-one in 768 scheme destroys Elo silently |
| Gauntlet checkpoint/resume | New JSON format | Extend existing `gauntlet.py` schema | Phase 3 atomic checkpoint already handles resume |
| Wilson CI | Custom binomial math | `gauntlet.wilson_ci` | Phase 3 proven helper |
| Elo measurement framework | SPRT/BayesElo dependency | Logistic map from score rate + Wilson bounds | Satisfies D-12 without new tools |

**Key insight:** The phase is integration and proof, not new ML or measurement science. Reuse Phase 3/4 contracts everywhere.

## Claude's Discretion — Recommendations

| Area | Recommendation | Rationale |
|------|----------------|-----------|
| **Net path** | `ance/eval/nnue/net.safetensors` resolved via `Path(__file__).with_name("net.safetensors")` | Colocated with eval code; matches D-05 example; no packaging.toml change required if path is filesystem-relative to module |
| **Parity FEN suite** | **32 FENs**: 697 validation-shard samples (deterministic seed=42 subsample from Phase 4 val split) + 8 manual tactical FENs | Val positions are held-out from training; exact count matches power-of-two batch comfort; `@pytest.mark.torch` |
| **Symmetric FENs (D-14)** | `4k3/8/8/8/8/8/8/4K3 w - - 0 1` and `4k3/8/8/8/8/8/8/4K3 b - - 0 1` | Kings only, perfectly symmetric; NNUE has no tempo term — do **not** use startpos (handcrafted tempo convention differs) |
| **Color-mirror suite (D-15)** | 6 FENs: for each, compare `eval(fen)` vs `eval(mirror_colors_flip_stm(fen))` | Implementation helper using `chess.Board.mirror()` + turn flip |
| **SF sign suite (D-16)** | 8 positions (4 won / 4 lost), skip if `stockfish` not on PATH | Compare `sign(nnue_cp)` vs `sign(sf_score.relative)` only |
| **Search depth N** | **3** for ≥1000-game acceptance; Wave 0 benchmark confirms | ~0.33 s/search handcrafted @ d3; ~4–8 h projected with NNUE overhead; d4 ~20+ h |
| **Opening book** | Existing `ance/tools/openings.epd` (31 lines) unchanged | Phase 3 D-16 book; cycles for 1000 games via `(game_index // 2) % len(openings)` |
| **Elo formula** | Point: `elo = -400 * log10(1/score_rate - 1)` when score_rate ∈ (0,1); CI: apply same transform to Wilson `(low, high)` on score points; **pass if `elo > 0` and `elo_ci_low > 0`** | Monotonic with D-12; reuses existing Wilson on engine-A score rate |
| **Search-config diff** | (1) Structural grep tests (existing pattern); (2) checkpoint `parameters` records `search_depth`, argv, env keys — assert only `ANCE_EVAL` differs between A/B specs | Automates D-04 without fragile full binary diff |

## Common Pitfalls

### Pitfall 1: Weight layout transpose confusion

**What goes wrong:** Numpy matmul shape mismatch or parity off by large margin.  
**Why it happens:** PyTorch `nn.Linear` stores `(out, in)`; export transposes to `(in, out)` per `nnue_format/schema.py`.  
**How to avoid:** Use `features @ w["ft.weight"]` never `w["ft.weight"] @ features.T`; cross-check against `tests/training/test_export_pipeline_smoke.py`.  
**Warning signs:** Parity failures on every FEN, not just edge cases.

### Pitfall 2: Feature encoder drift from training

**What goes wrong:** Parity passes on startpos only but gauntlet Elo ≈ 0 or negative.  
**Why it happens:** `relative_square(square ^ 56)` perspective flip differs subtly from handcrafted PST mirroring.  
**How to avoid:** Copy `training/data/features.py` verbatim; add `test_engine_features_match_training_encoder` on ≥100 FENs.  
**Warning signs:** `encode_position` tests pass in training package but engine copy diverges.

### Pitfall 3: Side-to-move sign double-flip

**What goes wrong:** Color-mirror golden fails; search prefers wrong side.  
**Why it happens:** NNUE output is already STM-relative from dual-perspective architecture; applying an extra negation vs handcrafted's white-relative + flip pattern.  
**How to avoid:** NNUE `evaluate()` returns `cp_from_nnue_output(forward(...))` directly — **no** extra turn flip (unlike `HandcraftedEval`). Document in class docstring.  
**Warning signs:** D-15 passes for handcrafted adapter but fails for NNUE.

### Pitfall 4: Using clock gauntlet for TOOL-04

**What goes wrong:** Time forfeits dominate; Elo measures clock noise not eval quality.  
**Why it happens:** Copy-paste Phase 3 `--tc 30+0.3` invocation.  
**How to avoid:** Implement `--depth` mode first; evidence JSON records `"mode": "fixed_depth", "depth": N`.  
**Warning signs:** `time_forfeit` outcomes in checkpoint.

### Pitfall 5: Gauntlet env not passed to child process

**What goes wrong:** Both engines run handcrafted; Elo ≈ 0 with tight CI around 50%.  
**Why it happens:** `EngineSpec` only carries argv today; env vars inherited identically.  
**How to avoid:** Explicit `env` dict on `EngineSpec`; merge at `popen_uci`.  
**Warning signs:** Sanity check shows 50% ± noise despite intending NNUE vs HC.

### Pitfall 6: Invalid ANCE_EVAL silently ignored

**What goes wrong:** Typo `ANCE_EVAL=nnuee` runs handcrafted; false negative on Elo gate.  
**Why it happens:** Missing D-03 fail-fast.  
**How to avoid:** Validate before constructing evaluator; subprocess integration test expects exit code ≠ 0.  
**Warning signs:** stderr shows handcrafted paths when NNUE expected.

### Pitfall 7: Mate positions through NNUE

**What goes wrong:** Huge bogus cp from network on terminal positions.  
**Why it happens:** Net trained on non-mate positions; search normally handles terminals before eval.  
**How to avoid:** Rely on existing search terminal detection (negamax returns before leaf eval on mate/stalemate); optional assert eval not called at ply 0 mate tests.  
**Warning signs:** PV scores outside mate window in tactical tests.

## Code Examples

### Shared parity helper (tests)

```python
# tests/nnue_parity_helpers.py (new)
import numpy as np
import torch
from training.data.features import encode_position
from training.model import NNUE

def torch_cp_int(model: NNUE, fen: str) -> int:
    stm_np, opp_np = encode_position(fen)
    stm = torch.from_numpy(stm_np).unsqueeze(0)
    opp = torch.from_numpy(opp_np).unsqueeze(0)
    with torch.no_grad():
        raw = float(model(stm, opp).item())
    return int(round(raw))

def numpy_cp_int(nnue_eval, fen: str) -> int:
    from ance.board.position import Position
    import chess
    return nnue_eval.evaluate(Position(chess.Board(fen)))
```

### Default weight path resolution

```python
# ance/eval/nnue/eval.py
import os
from pathlib import Path
from nnue_format.io import load_net

_DEFAULT_NET = Path(__file__).with_name("net.safetensors")

class NnueEval:
    def __init__(self) -> None:
        path = os.environ.get("ANCE_NNUE_PATH", str(_DEFAULT_NET))
        if not Path(path).is_file():
            raise FileNotFoundError(f"NNUE weights not found: {path}")
        self.weights, self.meta = load_net(path)  # strict D-08
```

### Fail-fast env test (subprocess)

```python
def test_invalid_ance_eval_exits_nonzero():
    env = {**base_env, "ANCE_EVAL": "bogus"}
    proc = subprocess.run([sys.executable, "-m", "ance"], input="quit\n", env=env, ...)
    assert proc.returncode != 0
    assert "allowed" in proc.stderr.lower()
```

### Logistic Elo from Wilson score rate

```python
import math

def score_rate_to_elo(p: float) -> float:
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    return -400.0 * math.log10(1.0 / p - 1.0)

def elo_ci_from_wilson(low: float, high: float, n: int) -> tuple[float, float]:
    # low/high are Wilson bounds on fractional score (0..1), not raw points
    return score_rate_to_elo(low), score_rate_to_elo(high)
```

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/python -m pytest tests/test_nnue_eval.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` |
| Slow gauntlet | `.venv/bin/python -m pytest tests/test_phase5_elo_evidence.py -x -m slow` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-03 | NnueEval loads safetensors, implements Protocol | unit | `pytest tests/test_nnue_eval.py::test_nnue_loads_default_net -x` | ❌ Wave 0 |
| EVAL-03 | Torch↔numpy exact cp parity | integration (torch) | `pytest tests/test_nnue_eval.py -m torch -x` | ❌ Wave 0 |
| EVAL-03 | ANCE_EVAL fail-fast / wiring | subprocess | `pytest tests/test_nnue_eval.py::test_invalid_ance_eval_exits -x` | ❌ Wave 0 |
| EVAL-03 | D-14 symmetric = 0 | unit | `pytest tests/test_nnue_eval.py::test_symmetric_positions_score_zero -x` | ❌ Wave 0 |
| EVAL-03 | D-15 color-mirror equality | unit | `pytest tests/test_nnue_eval.py::test_color_mirror_stm_flip -x` | ❌ Wave 0 |
| EVAL-03 | D-16 SF sign agreement | integration | `pytest tests/test_nnue_eval.py::test_stockfish_sign_agreement -x` | ❌ Wave 0 |
| TOOL-04 | Gauntlet depth + env injection | unit | `pytest tests/test_nnue_gauntlet_depth.py -x` | ❌ Wave 0 |
| TOOL-04 | ≥1000-game Elo CI gate | slow e2e | `pytest tests/test_phase5_elo_evidence.py -m slow -x` | ❌ Wave 0 |
| TOOL-04 | Search-config diff (D-04) | structural | `pytest tests/test_nnue_eval.py::test_search_config_unchanged -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_nnue_eval.py -x -q` (and gauntlet unit tests when touched)
- **Per wave merge:** `pytest tests/ -q -m 'not slow'`
- **Phase gate:** full suite including `@pytest.mark.slow` TOOL-04 evidence green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `ance/eval/nnue/{features,inference,eval}.py` + `net.safetensors` copy
- [ ] `ance/uci/loop.py` — `resolve_evaluator()` + fail-fast
- [ ] `ance/tools/gauntlet.py` — `EngineSpec.env`, `--depth`, Elo fields in aggregate
- [ ] `tests/test_nnue_eval.py` — parity, goldens, env wiring
- [ ] `tests/test_nnue_gauntlet_depth.py` — harness contracts
- [ ] `tests/test_phase5_elo_evidence.py` — slow ≥1000-game gate + evidence JSON
- [ ] `tests/nnue_parity_helpers.py` — shared torch/numpy oracle (optional module)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V5 Input Validation | yes | Validate `ANCE_EVAL` against allowlist; `load_net` strict schema; malformed FEN already rejected by Position adapter |
| V6 Cryptography | no | Weights are public training artifacts, not secrets |
| V10 Malicious Code | partial | No `eval()` on env paths; load only via safetensors parser |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via `ANCE_NNUE_PATH` | Tampering | Open file only after `Path.is_file()`; no arbitrary code load — safetensors tensors only |
| Untrusted weight file | Tampering | Strict `arch_id` / shape validation in `load_net` (D-08) |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv | all | ✓ | 3.14.6 (torch 2.13.0) | — |
| NumPy / safetensors / chess | NnueEval + gauntlet | ✓ | see Standard Stack | — |
| PyTorch | parity tests only | ✓ | 2.13.0 | skip `@pytest.mark.torch` |
| Stockfish | D-16 sign tests | ✓ | `/opt/homebrew/bin/stockfish` | skip sign suite |
| cutechess-cli | optional runner (D-09) | ✗ | — | arbiter (default `detect_runner()`) |
| Phase 4 net | D-07 copy source | ✓ | 790 KB safetensors | — |

**Missing dependencies with no fallback:**
- none (arbiter satisfies TOOL-04 per D-09)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `int(round(float_output))` is the shared conversion both torch parity and `NnueEval` use | Code Examples | Parity passes but engine uses trunc → D-13 fail |
| A2 | Kings-only FENs score exactly 0 after training (symmetric positions) | D-14 recommendation | May need slightly wider symmetric suite or retrain |
| A3 | Depth 3 × 1000 games finishes overnight with NNUE overhead | Depth N | Run may need depth 2 or `--budget-seconds` resume |
| A4 | Logistic Elo from Wilson score rate satisfies stakeholder intent for "95% CI lower bound > 0" | Elo formula | May need BayesElo if user expects engine-Elo units from cutechess |

## Open Questions

1. **Should `nnue_format` gain a shared `features.py`?**
   - What we know: duplication risks drift; training encoder is authoritative.
   - Recommendation: duplicate in `ance/eval/nnue/` with exhaustive cross-test; defer package move to v2 cleanup.

2. **Package data / editable install resolution for default net path**
   - What we know: `pyproject.toml` has no `[tool.setuptools.package-data]` yet.
   - Recommendation: `Path(__file__).with_name("net.safetensors")` works for repo-relative runs and editable installs if file is on disk next to module (git-tracked).

## Sources

### Primary (HIGH confidence)
- Codebase: `ance/eval/base.py`, `ance/uci/loop.py`, `ance/tools/gauntlet.py`, `nnue_format/*`, `training/model.py`, `training/data/features.py`, `training/export.py`
- `.planning/phases/04-offline-nnue-training-pipeline/04-VERIFICATION.md` — approved net provenance
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-CONTEXT.md` — locked D-01..D-16

### Secondary (MEDIUM confidence)
- `/niklasf/python-chess` (Context7) — `Limit(depth=…)`, `SimpleEngine.popen_uci`
- Local benchmark — depth 2/3/4 timing on this machine (2026-07-18)

### Tertiary (LOW confidence)
- Logistic Elo mapping from score rate — standard chess statistics practice [ASSUMED]; satisfies D-12 numerically

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — pinned venv, no new packages
- Architecture: **HIGH** — direct extension of Phase 3/4 patterns; gauntlet gaps identified with concrete fixes
- Pitfalls: **HIGH** — transpose/encoder/sign issues verified against existing tests and export contract

**Research date:** 2026-07-18  
**Valid until:** ~2026-08-18 (stable stack; re-benchmark if search/eval changes)

---

## RESEARCH COMPLETE

**Phase:** 5 — NNUE Swap-In & Elo Gauntlet  
**Confidence:** HIGH

### Key Findings

- Phase 4 approved `net.safetensors` is ready to copy; `nnue_format.load_net` validates all D-08 fields today.
- Gauntlet must gain **fixed-depth mode** and **per-engine env injection** — current clock-only harness does not satisfy D-11/D-04.
- NumPy forward is a straight mirror of `training/model.py` using transposed weights from export; shared `cp_from_nnue_output(int(round))` satisfies D-13.
- Depth **3** is the recommended acceptance search depth (~4–8 h projected vs ~20+ h at depth 4 on this machine).
- Symmetric golden FENs should be **king-only**, not startpos (handcrafted tempo convention does not apply to NNUE).

### File Created

`.planning/phases/05-nnue-swap-in-elo-gauntlet/05-RESEARCH.md`

### Primary Recommendation

Implement `NnueEval` under `ance/eval/nnue/` with git-tracked `net.safetensors`, wire `ANCE_EVAL`/`ANCE_NNUE_PATH` fail-fast in `loop.py`, extend gauntlet for `--depth` + env-aware `EngineSpec`, then gate TOOL-04 on parity/golden pytest before the slow ≥1000-game run at depth 3 using logistic Elo + Wilson CI (lower bound > 0).
