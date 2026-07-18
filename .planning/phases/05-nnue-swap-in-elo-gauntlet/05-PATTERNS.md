# Phase 5: NNUE Swap-In & Elo Gauntlet - Pattern Map

**Mapped:** 2026-07-18
**Files analyzed:** 13 (11 code files + 1 binary asset + 1 optional helper)
**Analogs found:** 13 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ance/eval/nnue/eval.py` | service | transform | `ance/eval/handcrafted.py` | exact |
| `ance/eval/nnue/features.py` | utility | transform | `training/data/features.py` | exact |
| `ance/eval/nnue/inference.py` | service | transform | `training/model.py` | role-match |
| `ance/eval/nnue/__init__.py` | config | transform | `ance/eval/__init__.py` | exact |
| `ance/eval/nnue/net.safetensors` | config | file-I/O | `.planning/phases/04-offline-nnue-training-pipeline/run-output/net.safetensors` | exact |
| `ance/uci/loop.py` | controller | request-response | `ance/debug.py` + current `loop.py` | exact |
| `ance/tools/gauntlet.py` | service | batch | `ance/tools/gauntlet.py` (extend in place) | exact |
| `tests/test_nnue_eval.py` | test | transform | `tests/test_eval_seam.py` | exact |
| `tests/test_nnue_gauntlet_depth.py` | test | batch | `tests/test_gauntlet_harness.py` | exact |
| `tests/test_phase5_elo_evidence.py` | test | batch | `tests/test_phase3_gauntlet_evidence.py` | exact |
| `tests/nnue_parity_helpers.py` | utility | transform | `tests/training/test_export_pipeline_smoke.py` | role-match |

## Pattern Assignments

### `ance/eval/nnue/eval.py` (service, transform)

**Analog:** `ance/eval/handcrafted.py` (Evaluator implementation) + `nnue_format/io.py` (weight load)

**Imports pattern** (from `handcrafted.py` lines 13-17, `io.py` lines 8-12):

```python
from __future__ import annotations

import os
from pathlib import Path

import chess

from ance.board.position import Position
from nnue_format.io import load_net
from ance.eval.nnue.features import encode_position
from ance.eval.nnue.inference import cp_from_nnue_output, forward_cp_float
```

**Core Evaluator pattern** (from `handcrafted.py` lines 145-165 — satisfy Protocol, STM-relative return):

```python
class NnueEval:
    """Side-to-move-relative NNUE evaluator. Output is already STM-relative
    from the dual-perspective architecture — no extra turn flip (unlike
    HandcraftedEval's white-relative + sign flip)."""

    def evaluate(self, pos: Position) -> int:
        board = pos.board
        stm, opp = encode_position(board.fen())
        raw = forward_cp_float(stm, opp, self.weights)
        return cp_from_nnue_output(raw)
```

**Weight load + fail-fast pattern** (from `nnue_format/io.py` lines 28-53, RESEARCH D-05/D-06):

```python
_DEFAULT_NET = Path(__file__).with_name("net.safetensors")

def __init__(self) -> None:
    path = os.environ.get("ANCE_NNUE_PATH", str(_DEFAULT_NET))
    if not Path(path).is_file():
        raise FileNotFoundError(f"NNUE weights not found: {path}")
    self.weights, self.meta = load_net(path)  # strict D-08 validation inside
```

**Error handling:** Let `load_net` raise `ValueError` on schema/shape mismatch; do not catch and fall back to handcrafted (D-06). Propagate `FileNotFoundError` to `loop.py` startup.

---

### `ance/eval/nnue/features.py` (utility, transform)

**Analog:** `training/data/features.py` (authoritative encoder — copy verbatim)

**Imports pattern** (lines 8-11):

```python
from __future__ import annotations

import numpy as np
import chess
```

**Core transform pattern** (lines 16-57 — entire module body is the pattern):

```python
NUM_FEATURES = 768

def piece_type_index(piece_type: int) -> int:
    return piece_type - 1

def relative_square(square: int, perspective: bool) -> int:
    if perspective == chess.WHITE:
        return square
    return square ^ 56

def feature_index(
    perspective: bool,
    piece_square: int,
    piece_type: int,
    piece_color: bool,
) -> int:
    relative_color = 0 if piece_color == perspective else 1
    return (
        relative_color * 384
        + piece_type_index(piece_type) * 64
        + relative_square(piece_square, perspective)
    )

def encode_perspective(board: chess.Board, perspective: bool) -> np.ndarray:
    features = np.zeros(NUM_FEATURES, dtype=np.float32)
    for square, piece in board.piece_map().items():
        index = feature_index(
            perspective,
            square,
            piece.piece_type,
            piece.color,
        )
        features[index] = 1.0
    return features

def encode_position(fen: str) -> tuple[np.ndarray, np.ndarray]:
    board = chess.Board(fen)
    stm = board.turn
    opp = not stm
    return encode_perspective(board, stm), encode_perspective(board, opp)
```

**Validation:** Cross-test against `training.data.features.encode_position` on ≥100 FENs (pattern from `tests/training/test_features_encoding.py`).

---

### `ance/eval/nnue/inference.py` (service, transform)

**Analog:** `training/model.py` (torch forward) + `nnue_format/schema.py` (transposed weight layout)

**Imports pattern** (lines 7-9 of `model.py`, schema constants):

```python
from __future__ import annotations

import numpy as np
```

**Core forward pattern** (mirror `training/model.py` lines 28-34 using transposed weights per `schema.py` lines 6-13):

```python
def forward_cp_float(
    stm: np.ndarray, opp: np.ndarray, weights: dict[str, np.ndarray]
) -> float:
    # Weights already transposed at export: features @ weight + bias
    stm_h = np.clip(stm @ weights["ft.weight"] + weights["ft.bias"], 0.0, 1.0)
    opp_h = np.clip(opp @ weights["ft.weight"] + weights["ft.bias"], 0.0, 1.0)
    combined = np.concatenate([stm_h, opp_h])  # (512,)
    return float(combined @ weights["out.weight"] + weights["out.bias"])

def cp_from_nnue_output(raw: float) -> int:
    """Shared float→int conversion for D-13 parity (round-to-nearest)."""
    return int(round(raw))
```

**Anti-pattern:** Never transpose weights at inference — export already stores `(in, out)` shapes (`schema.EXPECTED_SHAPES`).

---

### `ance/eval/nnue/__init__.py` (config, transform)

**Analog:** `ance/eval/__init__.py`

**Package docstring pattern** (lines 1-8):

```python
"""NNUE evaluation package (EVAL-03).

`ance.eval.nnue.eval` provides `NnueEval`, the zero-torch `(768→256)×2→1`
evaluator wired behind the `Evaluator` Protocol seam. Weights load via
`nnue_format.io.load_net`; feature encoding mirrors
`training/data/features.py` bit-for-bit.
"""

from __future__ import annotations

from ance.eval.nnue.eval import NnueEval

__all__ = ["NnueEval"]
```

---

### `ance/eval/nnue/net.safetensors` (config, file-I/O)

**Analog:** `.planning/phases/04-offline-nnue-training-pipeline/run-output/net.safetensors`

**Copy contract:** Binary copy per D-07; validate after copy with `nnue_format.io.load_net` (pattern from `tests/training/test_export_pipeline_smoke.py` lines 38-44):

```python
arrays, meta = nnue_io.load_net(str(path))
assert arrays["ft.weight"].shape == (768, 256)
assert arrays["out.weight"].shape == (512, 1)
assert meta["arch_id"] == schema.ARCH_ID
assert meta["feature_set"] == schema.FEATURE_SET
```

**Resolution pattern:** `Path(__file__).with_name("net.safetensors")` next to `eval.py` (RESEARCH recommendation).

---

### `ance/uci/loop.py` (controller, request-response) — MODIFY

**Analog:** `ance/debug.py` (env-var lifecycle) + existing module-level evaluator wiring (lines 70-73)

**Env-var read pattern** (from `debug.py` lines 11-16):

```python
import os
import sys

_ALLOWED_EVAL = frozenset({"handcrafted", "nnue"})

def resolve_evaluator() -> Evaluator:
    mode = os.environ.get("ANCE_EVAL", "handcrafted")
    if mode not in _ALLOWED_EVAL:
        print(
            f"error: invalid ANCE_EVAL={mode!r}; allowed: {sorted(_ALLOWED_EVAL)}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if mode == "nnue":
        from ance.eval.nnue.eval import NnueEval
        return NnueEval()
    from ance.eval.handcrafted import HandcraftedEval
    return HandcraftedEval()
```

**Startup wiring pattern** (replace lines 70-73):

```python
evaluator: Evaluator = resolve_evaluator()
```

**Fail-fast on NNUE load:** Wrap `NnueEval()` construction; on `FileNotFoundError`/`ValueError`, print to stderr and `sys.exit(1)` — no silent handcrafted fallback (D-06).

**Keep unchanged:** Search thread passes `evaluator` by Protocol reference (lines 127-156); no argparse (D-01).

---

### `ance/tools/gauntlet.py` (service, batch) — MODIFY

**Analog:** Existing `gauntlet.py` — extend `EngineSpec`, `play_gauntlet_game`, `_parameters`, `_aggregate`, `_build_parser`

**EngineSpec env injection pattern** (extend lines 48-53):

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class EngineSpec:
    name: str
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
```

**Subprocess env merge pattern** (replace lines 404-405 — analog: `tests/conftest.py` lines 89-97, `test_go_bestmove.py` lines 47-56):

```python
base_env = os.environ.copy()
engine_a = chess.engine.SimpleEngine.popen_uci(
    spec_a.argv, env={**base_env, **spec_a.env}
)
engine_b = chess.engine.SimpleEngine.popen_uci(
    spec_b.argv, env={**base_env, **spec_b.env}
)
```

**Fixed-depth limit pattern** (extend `play_gauntlet_game` — currently clock-only at lines 129-136):

```python
# When search_depth is set (D-11), use depth limit instead of wall clocks:
limit = chess.engine.Limit(depth=search_depth)
play_result = engines[mover].play(board, limit, game=game_key)
```

**Checkpoint parameters pattern** (extend `_parameters` lines 210-230):

```python
return {
    # ... existing fields ...
    "mode": "fixed_depth" if search_depth is not None else "clock",
    "search_depth": search_depth,
    "engine_a": {"name": spec_a.name, "argv": list(spec_a.argv), "env": dict(spec_a.env)},
    "engine_b": {"name": spec_b.name, "argv": list(spec_b.argv), "env": dict(spec_b.env)},
}
```

**Elo reporting extension** (extend `_aggregate` lines 263-288 — add logistic Elo from score rate):

```python
def score_rate_to_elo(p: float) -> float:
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    return -400.0 * math.log10(1.0 / p - 1.0)

# In _aggregate after wilson_ci:
score_rate = score_points / n if n else 0.0
low, high = wilson_ci(score_points, n)
elo = score_rate_to_elo(score_rate)
elo_ci_low = score_rate_to_elo(low)
elo_ci_high = score_rate_to_elo(high)
```

**CLI extension** (extend `_build_parser` lines 526-546):

```python
parser.add_argument("--depth", type=int, default=None, help="Fixed go depth N (D-11)")
```

**Reuse unchanged:** `wilson_ci` (lines 73-87), `_atomic_write_json` (lines 291-299), color-paired opening index `(game_index // 2) % len(openings)` (line 408), `detect_runner()` (lines 464-466).

---

### `tests/test_nnue_eval.py` (test, transform)

**Analog:** `tests/test_eval_seam.py` + `tests/training/test_export_pipeline_smoke.py` + `tests/training/test_stockfish_labeler.py`

**Imports pattern** (from `test_eval_seam.py` lines 10-26):

```python
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import chess
import pytest

from ance.board.position import Position
from ance.eval.nnue.eval import NnueEval
```

**Symmetric golden pattern** (adapt from `test_eval_seam.py` lines 35-43 — use king-only FENs, not startpos):

```python
SYMMETRIC_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

def test_symmetric_positions_score_zero() -> None:
    nnue = NnueEval()
    assert nnue.evaluate(Position(chess.Board(SYMMETRIC_FEN))) == 0
    black_stm = chess.Board(SYMMETRIC_FEN)
    black_stm.turn = chess.BLACK
    assert nnue.evaluate(Position(black_stm)) == 0
```

**Color-mirror pattern** (new — use `chess.Board.mirror()` + turn flip for D-15):

```python
def test_color_mirror_stm_flip() -> None:
    nnue = NnueEval()
    board = chess.Board("rnbqkbnr/pppp1ppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    original = nnue.evaluate(Position(board))
    mirrored = board.mirror()
    mirrored.turn = not board.turn
    assert nnue.evaluate(Position(mirrored)) == original
```

**Structural seam proof** (from `test_eval_seam.py` lines 91-97, extend for NnueEval):

```python
def test_negamax_module_never_imports_a_concrete_evaluator() -> None:
    source = Path("ance/search/negamax.py").read_text()
    non_comment = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "NnueEval" not in non_comment
    assert "HandcraftedEval" not in non_comment
```

**Torch parity pattern** (from `test_export_pipeline_smoke.py` lines 7-8, 17-44):

```python
pytest.importorskip("torch")
pytestmark_torch = pytest.mark.torch

@pytest.mark.torch
def test_torch_numpy_parity_on_held_out_fens(fen: str) -> None:
    # Compare int(round(torch_forward)) == NnueEval().evaluate(Position(...))
    ...
```

**Fail-fast subprocess pattern** (from `tests/conftest.py` lines 89-97):

```python
def test_invalid_ance_eval_exits_nonzero() -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("ANCE_EVAL", "ANCE_DEBUG")}
    env["ANCE_EVAL"] = "bogus"
    proc = subprocess.run(
        [sys.executable, "-m", "ance"],
        input="quit\n",
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode != 0
    assert "allowed" in proc.stderr.lower()
```

**Stockfish sign pattern** (from `test_stockfish_labeler.py` lines 16-19, 24-31):

```python
pytestmark_sf = pytest.mark.skipif(
    shutil.which("stockfish") is None,
    reason="stockfish binary not on PATH",
)

@pytest.mark.skipif(shutil.which("stockfish") is None, reason="...")
def test_stockfish_sign_agreement() -> None:
    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:
        info = engine.analyse(chess.Board(fen), chess.engine.Limit(depth=12))
        sf_cp = info["score"].white().score(mate_score=10000)
    nnue_cp = NnueEval().evaluate(Position(chess.Board(fen)))
    assert (sf_cp > 0) == (nnue_cp > 0)
```

---

### `tests/test_nnue_gauntlet_depth.py` (test, batch)

**Analog:** `tests/test_gauntlet_harness.py`

**Mock engine pattern** (lines 17-30):

```python
class _ScriptedEngine:
    def __init__(self, moves: list[str]) -> None:
        self.moves = iter(moves)
        self.limits: list[object] = []

    def play(self, board: chess.Board, limit: object, *, game: object) -> object:
        self.limits.append(limit)
        return SimpleNamespace(move=chess.Move.from_uci(next(self.moves)))
```

**Depth limit assertion pattern** (adapt from lines 44-75):

```python
def test_fixed_depth_uses_limit_depth_not_clocks(monkeypatch) -> None:
    white = _ScriptedEngine(["e2e4"])
    black = _ScriptedEngine(["e7e5"])
    record = gauntlet.play_gauntlet_game(
        white, black, chess.STARTING_FEN,
        search_depth=3,  # new param
        max_halfmoves=20,
        game_key="g0",
        stop_event=None,
        deadline=None,
    )
    assert white.limits[0].depth == 3
    assert white.limits[0].white_clock is None  # no clock when depth mode
```

**Env injection spy pattern** (adapt from lines 78-123 — monkeypatch `popen_uci` to capture env):

```python
captured_envs: list[dict] = []
monkeypatch.setattr(
    gauntlet.chess.engine.SimpleEngine,
    "popen_uci",
    lambda argv, **kwargs: (captured_envs.append(kwargs.get("env", {})), _ScriptedEngine([]))[1],
)
gauntlet.run_gauntlet(
    gauntlet.EngineSpec("hc", ENGINE_ARGV, env={"ANCE_EVAL": "handcrafted"}),
    gauntlet.EngineSpec("nnue", ENGINE_ARGV, env={"ANCE_EVAL": "nnue"}),
    openings, n_games=2, search_depth=3, ...
)
assert captured_envs[0]["ANCE_EVAL"] == "handcrafted"
assert captured_envs[1]["ANCE_EVAL"] == "nnue"
```

**Checkpoint parameter diff pattern** (adapt from lines 134-214 — assert only `ANCE_EVAL` differs):

```python
params = report["parameters"]
assert params["engine_a"]["argv"] == params["engine_b"]["argv"]
assert set(params["engine_a"]["env"].keys()) ^ set(params["engine_b"]["env"].keys()) == set()
assert params["engine_a"]["env"].get("ANCE_EVAL") == "handcrafted"
assert params["engine_b"]["env"].get("ANCE_EVAL") == "nnue"
```

---

### `tests/test_phase5_elo_evidence.py` (test, batch)

**Analog:** `tests/test_phase3_gauntlet_evidence.py`

**Constants + engine argv pattern** (lines 19-24):

```python
D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
```

**Pass gate helpers** (adapt D-12 from lines 27-42):

```python
def assert_positive_elo_with_ci(report: dict) -> None:
    agg = report["aggregate"]
    assert agg["elo"] > 0, f"D-12 point estimate not positive: {agg['elo']}"
    assert agg["elo_ci_low"] > 0, f"D-12 CI lower bound not > 0: {agg['elo_ci_low']}"
```

**Slow-marked evidence run pattern** (lines 102-206):

```python
@pytest.mark.slow
def test_phase5_thousand_game_nnue_vs_handcrafted_evidence(tmp_path: Path) -> None:
    checkpoint = Path(os.environ.get("ANCE_PHASE5_GAUNTLET_CHECKPOINT", tmp_path / "p5-checkpoint.json"))
    evidence_path = Path(os.environ.get(
        "ANCE_PHASE5_GAUNTLET_EVIDENCE",
        ".planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json",
    ))
    spec_nnue = gauntlet.EngineSpec("nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"})
    spec_hc = gauntlet.EngineSpec("handcrafted", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"})
    report = gauntlet.run_gauntlet(
        spec_nnue, spec_hc,
        gauntlet.load_openings(gauntlet.DEFAULT_OPENINGS),
        n_games=D12_GAMES,
        search_depth=SEARCH_DEPTH,
        max_halfmoves=MAX_HALFMOVES,
        output_path=checkpoint,
        openings_path=gauntlet.DEFAULT_OPENINGS,
        command_line=shlex.join([...]),
    )
    assert_positive_elo_with_ci(report)
    # Write evidence JSON with git_commit, gates_passed=["D-12", "TOOL-04"], mode/depth fields
```

**Evidence JSON schema pattern** (lines 179-205):

```python
evidence = {
    "schema_version": 1,
    "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "captured_utc": datetime.now(UTC).isoformat(),
    "gauntlet": {
        "games": aggregate["n_games"],
        "mode": "fixed_depth",
        "depth": SEARCH_DEPTH,
        "elo": aggregate["elo"],
        "elo_ci_low": aggregate["elo_ci_low"],
        "elo_ci_high": aggregate["elo_ci_high"],
        "score_rate": aggregate["score_rate"],
        "wilson_low": aggregate["wilson_low"],
        "wilson_high": aggregate["wilson_high"],
        "runner": gauntlet.detect_runner(),
        "command_line": report["command_line"],
    },
    "gates_passed": ["D-12", "TOOL-04"],
}
```

---

### `tests/nnue_parity_helpers.py` (utility, transform) — optional

**Analog:** `tests/training/test_export_pipeline_smoke.py` + RESEARCH Code Examples

**Imports pattern:**

```python
from __future__ import annotations

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

**Boundary:** Torch imports allowed here (under `tests/` only); never import from `ance/`.

---

## Shared Patterns

### Evaluator Protocol Seam
**Source:** `ance/eval/base.py`
**Apply to:** `NnueEval`, all eval tests, structural grep tests

```python
class Evaluator(Protocol):
    def evaluate(self, pos: Position) -> int:
        """Centipawns, side-to-move relative (positive = side to move is
        better)."""
        ...
```

### Zero-Torch / No-Training Boundary
**Source:** `tests/training/test_no_torch_leakage.py`
**Apply to:** All `ance/eval/nnue/*` files, `loop.py`

```python
def test_ance_never_imports_training_package() -> None:
    ance_root = Path("ance")
    for path in sorted(ance_root.rglob("*.py")):
        offenders = [
            line.strip()
            for line in path.read_text().splitlines()
            if re.match(r"^\s*(?:import\s+training\b|from\s+training\b)", line)
        ]
        assert not offenders, f"{path} must not import training: {offenders}"
```

### Env-Var Configuration Lifecycle
**Source:** `ance/debug.py`
**Apply to:** `loop.py` (`ANCE_EVAL`, `ANCE_NNUE_PATH`), gauntlet `EngineSpec.env`

```python
_enabled: bool = bool(os.environ.get("ANCE_DEBUG"))

# Phase 5 mirrors this: read once at module init, stderr for errors, no stdout pollution
```

### Safetensors Load Contract
**Source:** `nnue_format/io.py` + `nnue_format/schema.py`
**Apply to:** `NnueEval.__init__`, parity tests

```python
if meta.get("arch_id") != schema.ARCH_ID:
    raise ValueError(...)
for name, expected_shape in schema.EXPECTED_SHAPES.items():
    if actual_shape != expected_shape:
        raise ValueError(...)
```

### Subprocess UCI + Custom Env
**Source:** `tests/conftest.py` lines 83-98
**Apply to:** Fail-fast env tests, gauntlet engine launch

```python
env = {k: v for k, v in os.environ.items() if k != "ANCE_DEBUG"}
env["ANCE_EVAL"] = "nnue"
process = subprocess.Popen(
    [sys.executable, "-m", "ance"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    env=env,
)
```

### Wilson CI + Checkpoint Atomicity
**Source:** `ance/tools/gauntlet.py`
**Apply to:** TOOL-04 reporting, evidence tests

```python
def wilson_ci(score_points: float, n: int, z: float = 1.96) -> tuple[float, float]:
    ...

def _atomic_write_json(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    ...
    os.replace(temporary, path)
```

### Weight Export Transpose (reference only — do not re-transpose at inference)
**Source:** `training/export.py` lines 19-24

```python
arrays = {
    "ft.weight": state["ft.weight"].T.contiguous().cpu().numpy().astype(np.float32),
    "out.weight": state["output.weight"].T.contiguous().cpu().numpy().astype(np.float32),
}
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All Phase 5 files have close analogs in existing codebase |

## Metadata

**Analog search scope:** `ance/eval/`, `ance/uci/`, `ance/tools/`, `nnue_format/`, `training/`, `tests/`
**Files scanned:** ~25 source/test files
**Pattern extraction date:** 2026-07-18
