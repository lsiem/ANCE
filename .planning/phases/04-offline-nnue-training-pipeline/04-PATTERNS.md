# Phase 4: Offline NNUE Training Pipeline - Pattern Map

**Mapped:** 2026-07-13
**Files analyzed:** 19 (training/ + nnue_format/ + tests/training/)
**Analogs found:** 4 in-repo (contract/convention analogs) / 19 — the rest have **no in-repo analog** and must be built from RESEARCH.md §Code Examples, which is itself the authoritative source (this is a net-new torch subsystem in an otherwise torch-free repo).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `nnue_format/schema.py` | config/model (contract constants) | transform | `ance/eval/base.py` (Evaluator Protocol + MATE constant) | contract-convention match (no structural analog) |
| `nnue_format/io.py` | utility (serialization) | file-I/O | none in-repo | no analog — use RESEARCH.md Pattern 5 verbatim |
| `training/mps_gate.py` | utility (device probe) | request-response (one-shot check) | none in-repo | no analog — use RESEARCH.md Code Example verbatim |
| `training/model.py` | model (torch nn.Module) | transform | none in-repo | no analog — use RESEARCH.md Pattern 1 verbatim |
| `training/train.py` | service (train loop) | batch | none in-repo | no analog — use RESEARCH.md Pattern 4 + Architecture Diagram |
| `training/export.py` | service (adapter to contract) | transform → file-I/O | none in-repo; consumes `nnue_format.save_net` | no analog |
| `training/label/stockfish_labeler.py` | service (subprocess driver) | request-response | none in-repo (project's own `chess.engine` usage is absent — only used elsewhere to drive Stockfish/opponents via CLI tools, not via Python) | no analog — RESEARCH.md Code Example is authoritative |
| `training/label/position_source.py` | utility | batch | none in-repo | no analog |
| `training/data/lichess_ingest.py` | service (ETL) | streaming | none in-repo | no analog — RESEARCH.md Code Example, watch Pitfall #3 sign flip |
| `training/data/merge.py` | utility (dedup) | batch/transform | none in-repo | no analog |
| `training/data/split.py` | utility (partition) | batch | none in-repo | no analog — RESEARCH.md Pattern 2 verbatim |
| `training/data/kfit.py` | utility (calibration) | batch | none in-repo | no analog — RESEARCH.md Pattern 3 verbatim |
| `training/data/features.py` | utility (encoder) | transform | `ance/board/position.py` (`Position` wraps `chess.Board`; feature extraction reads board state the same way) | role-match (read pattern only, not board-mutation pattern) |
| `training/data/shards.py` | utility (DataLoader/on-disk format) | batch/file-I/O | none in-repo | no analog (Claude's discretion per CONTEXT.md) |
| `training/run_manifest.py` | utility (provenance record) | file-I/O | none in-repo | no analog |
| `tests/training/conftest.py` | test (fixture/skip-gate) | request-response | `tests/conftest.py` (`EngineProcess` fixture file — establishes the project's fixture-file convention, though its actual fixture is unrelated) | structural-convention match (file location + role), not content |
| `tests/training/test_mps_gate.py` | test | request-response | `tests/test_eval_seam.py` (structural/behavioral pytest style, plain function tests, no test classes) | style-convention match |
| `tests/training/test_split_no_leakage.py` | test | batch | `tests/test_eval_seam.py` | style-convention match |
| `tests/training/test_nnue_format_roundtrip.py` | test | file-I/O | `tests/test_eval_seam.py` | style-convention match |

## Pattern Assignments

### `nnue_format/schema.py` + `nnue_format/io.py` (utility, file-I/O — the shared contract)

**Analog for the *contract-as-seam* convention:** `ance/eval/base.py`

**Why this is the right analog even though it's not code-shape-similar:** `ance/eval/base.py` is this project's only prior example of "a tiny, dependency-free module whose entire job is to be a stable seam between two halves of the system that must never import each other's internals." `nnue_format/` plays the identical architectural role between `training/` (torch) and the future `ance/eval/nnue/` (Phase 5, numpy-only) — same shape of problem, different domain.

**Contract-module shape to copy** (`ance/eval/base.py` lines 1-21):
```python
"""The `Evaluator` Protocol -- THE swap seam (D-00a, EVAL-01)...."""
from __future__ import annotations
from typing import Protocol
from ance.board.position import Position

MATE = 30000  # shared, documented-once constant; every module importing a
              # cross-boundary constant imports THIS one rather than redefining it
```
Mirror this for `nnue_format/schema.py`: define `ARCH_ID = "768x2-256-1"`, `FEATURE_SET = "board768"`, and expected shapes as **module-level constants documented once**, imported by both `training/export.py` and (Phase 5) `ance/eval/nnue/`. Do not let either side re-derive these strings/shapes locally — same discipline as `MATE` above.

**Docstring convention to copy:** every ANCE module in this repo opens with a triple-quoted module docstring naming the decision ID it satisfies (e.g. "D-00a, EVAL-01") and cross-referencing the enforcing test. `nnue_format/schema.py` and `io.py` should open the same way, citing D-07/TRN-04.

**Concrete implementation (no in-repo analog for the I/O logic itself — copy verbatim from RESEARCH.md Pattern 5, `.planning/phases/04-offline-nnue-training-pipeline/04-RESEARCH.md` lines 352-380):** the `save_net`/`load_net` functions using `safetensors.numpy.save_file`/`safe_open(..., framework="numpy")`, validating `arch_id`/`feature_set`/shapes and raising `ValueError` on mismatch ("fails loudly" — matches this repo's general `try_set_fen`-style "reject and keep, never reject and reset" discipline from `ance/board/position.py`, i.e. validate before committing/writing).

---

### `training/data/features.py` (utility, transform)

**Analog:** `ance/board/position.py`

**Read pattern to copy** (`ance/board/position.py` lines 21-32):
```python
def __init__(self, board: chess.Board | None = None) -> None:
    self._board: chess.Board = board if board is not None else chess.Board()

def legal_moves(self) -> list[chess.Move]:
    return list(self._board.legal_moves)

@property
def board(self) -> chess.Board:
    return self._board
```
`features.py`'s FEN→768-index encoder should read board state the same way `Position` does — via `chess.Board(fen)` and its `piece_map()`/`piece_at(square)` accessors — never re-deriving square/piece indices ad hoc. Since `training/` cannot import `ance/` (the "never shipped into runtime" rule, and more importantly `ance/eval/nnue/`'s Phase-5 feature encoder must independently match this one bit-for-bit), **do not import `ance.board.position.Position` from `training/`** — instead have `features.py` build its own minimal `chess.Board(fen)` reader that mirrors `Position`'s access style. Note in the module docstring that this encoding must stay in lockstep with whatever Phase 5's `ance/eval/nnue/features.py` implements (same 64×6×2 = 768 indexing scheme) — RESEARCH.md's Architecture Diagram calls this out explicitly ("mirrors `ance/eval/nnue/features.py` spec").

---

### `training/model.py`, `training/mps_gate.py`, `training/train.py`, `training/export.py`, `training/label/*`, `training/data/{lichess_ingest,merge,split,kfit,shards}.py`

**No in-repo analog** — this is the correct outcome, not a gap: the existing `ance/` tree is deliberately torch-free (PROJECT.md/ARCHITECTURE.md), and no prior phase has done ETL, subprocess-driven labeling, or model training. Do not force-fit an analog from `ance/tools/gauntlet.py` or `ance/tools/depth_vs_depth_match.py` (those drive Stockfish as an *opponent* via `chess.engine.SimpleEngine.popen_uci` for gameplay, not as a *labeler* for scoring) — the shapes diverge too much past the shared `popen_uci` call to be useful as a copy source.

**Use `04-RESEARCH.md` verbatim as the pattern source for each:**
- `training/model.py` ← RESEARCH.md Pattern 1 (lines 249-273): `NNUE(nn.Module)` with `ClippedReLU`, two-perspective concat `[stm_acc, opp_acc]`.
- `training/mps_gate.py` ← RESEARCH.md Code Example (lines 450-491): `select_device()` + `cpu_vs_mps_parity_check()`.
- `training/train.py` ← RESEARCH.md Pattern 4 (lines 332-345): `wdl_loss()` with the `has_result`-gated lambda blend.
- `training/label/stockfish_labeler.py` ← RESEARCH.md Code Example (lines 496-513): `label_position()`/`run_labeling()`, reading `info["score"].relative` — **never** an internal-eval path.
- `training/data/lichess_ingest.py` ← RESEARCH.md Code Example (lines 518-549): `iter_games()`/`extract_samples()`, **must** include the Pitfall-#3 sign flip (`if not stm_is_white: cp = -cp`) — this is the single most load-bearing line in the whole ingestion path; do not lose it during implementation.
- `training/data/split.py` ← RESEARCH.md Pattern 2 (lines 282-301): `split_by_game()` + `assert_no_fen_leakage()`.
- `training/data/kfit.py` ← RESEARCH.md Pattern 3 (lines 309-323): `fit_k()` via `scipy.optimize.curve_fit`, fit on `has_result` rows only.
- `training/export.py` calls `nnue_format.save_net(arrays, meta)` with `meta` including `k_scale`, `arch_id`, `feature_set`, `format_version` per RESEARCH.md line 382.

**Import-block convention to copy from the repo's general style** (seen in `ance/board/position.py` / `ance/eval/base.py`): `from __future__ import annotations` first, then stdlib, then third-party, then local — every `training/` module should keep this ordering even though `training/` is a separate top-level.

---

### `tests/training/` package (test, request-response / batch / file-I/O)

**Analog:** `tests/test_eval_seam.py` + `tests/conftest.py`

**Structural convention to copy from `tests/test_eval_seam.py`:**
```python
"""Tests proving the Evaluator seam (D-00a) is a real, swappable boundary.
...structural proof that ance/search/negamax.py never imports a concrete evaluator..."""
from __future__ import annotations
import chess
from ance.board.position import Position
...

def test_negamax_module_never_imports_a_concrete_evaluator() -> None:
    source = Path("ance/search/negamax.py").read_text()
    non_comment_source = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "MaterialEval" not in non_comment_source
```
- Plain module-level `def test_...() -> None:` functions, no test classes, one behavior per test, docstring/comment explaining *why* the specific FEN or fixture was chosen (this repo does this consistently — see the PST reference-cell comment in the same file).
- This project already has a precedent for a **structural/seam-enforcing test** (reading source text and asserting an import never appears) — this is exactly the shape needed for "training/ MUST NOT be importable from ance/": add a mirrored test, e.g. `test_ance_never_imports_training()`, asserting no file under `ance/` contains the string `"training"` in an import line (or, more robustly, `import ance` succeeds in a subprocess with `training/` deleted from `sys.path`/not installed).
- `tests/training/conftest.py` should follow `tests/conftest.py`'s file-placement convention (co-located fixture file, module docstring explaining the *design reason* for the fixture) but its actual content is new: `pytest.importorskip("torch")` at collection time for torch-dependent test modules, while `test_nnue_format_roundtrip.py` must NOT call this skip (RESEARCH.md Validation Architecture, Wave-0 Gaps).
- **`pyproject.toml`** already has `[tool.pytest.ini_options] testpaths = ["tests"]` and a `slow` marker convention (`markers = ["slow: 100-game self-play gauntlet (deselect with -m 'not slow')"]`). Follow this exact pattern to add any new marker this phase needs (e.g. a `torch` marker), rather than inventing a different mechanism — RESEARCH.md's Validation Architecture section already recommends this.

---

## Shared Patterns

### Docstring-cites-decision-ID convention
**Source:** every existing `ance/` module (`ance/eval/base.py`, `ance/board/position.py`)
**Apply to:** every new `training/` and `nnue_format/` file — open with a triple-quoted docstring naming the CONTEXT.md decision ID(s) (D-01…D-09, TRN-01…TRN-05) it implements, and cross-reference the test that enforces it, exactly as `ance/eval/base.py` cites "D-00a, EVAL-01" and points at `test_negamax_module_never_imports_a_concrete_evaluator`.

### "Validate before commit, never partially mutate" convention
**Source:** `ance/board/position.py::try_set_fen` / `try_push_uci_moves` (build a candidate locally, only assign `self._board` on full success)
**Apply to:** `nnue_format/io.py::save_net` (write to a temp path and rename, or at minimum validate arrays/meta before calling `safetensors.numpy.save_file`) and `training/data/split.py` (build both train/val lists fully before running the disjointness assertion, never yield partially-split data) — same "reject and keep" discipline the codebase already applies to malformed FEN/move input, extended here to malformed/incomplete training artifacts.

### Structural seam-enforcement test
**Source:** `tests/test_eval_seam.py::test_negamax_module_never_imports_a_concrete_evaluator`
**Apply to:** a new `tests/training/test_no_torch_leakage.py` (or similar) proving no file under `ance/` imports anything from `training/`, and that `nnue_format/` itself has zero `import torch` anywhere (grep-based structural assertion, same style).

### Plain-function pytest style, no classes, `-> None:` everywhere
**Source:** `tests/test_eval_seam.py` (every single test)
**Apply to:** all new `tests/training/*.py`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `training/model.py` | model | transform | No torch code anywhere in the repo; RESEARCH.md Pattern 1 is authoritative |
| `training/mps_gate.py` | utility | request-response | No device-probing code exists; RESEARCH.md Code Example is authoritative |
| `training/train.py` | service | batch | No training loop exists; RESEARCH.md Pattern 4 is authoritative |
| `training/export.py` | service | transform/file-I/O | No prior export path; composes `nnue_format.save_net` |
| `training/label/stockfish_labeler.py` | service | request-response | Existing `chess.engine` usages (`ance/tools/gauntlet.py`, `depth_vs_depth_match.py`) drive Stockfish as a *game opponent*, not a *position labeler* — divergent enough to skip as an analog; use RESEARCH.md Code Example |
| `training/data/lichess_ingest.py` | service | streaming | No PGN-corpus ETL exists anywhere in the repo |
| `training/data/merge.py`, `split.py`, `kfit.py`, `shards.py` | utility | batch | No dataset-engineering code exists; RESEARCH.md Patterns 2-3 + Claude's-discretion shard format |
| `training/data/position_source.py`, `run_manifest.py` | utility | batch/file-I/O | Net-new provenance/sourcing concerns, no analog needed beyond RESEARCH.md's Architecture Diagram description |

## Metadata

**Analog search scope:** `ance/` (all subpackages), `tests/` (all test files + `conftest.py`), `pyproject.toml`
**Files scanned:** `ance/eval/base.py`, `ance/eval/material.py` (referenced via test), `ance/board/position.py`, `ance/search/negamax.py` (referenced via test), `tests/test_eval_seam.py`, `tests/conftest.py`, `pyproject.toml`, plus a directory listing of all of `ance/` and `tests/`
**Pattern extraction date:** 2026-07-13
**Primary non-repo source (used for all torch/nnue_format-specific logic, by design — no in-repo precedent exists):** `.planning/phases/04-offline-nnue-training-pipeline/04-RESEARCH.md` §Architecture Patterns (Patterns 1-5), §Code Examples, §Recommended Project Structure
</content>
