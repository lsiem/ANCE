"""The evaluation package -- the swappable Evaluator seam (D-00a, EVAL-01).

`ance.eval.base` defines the `Evaluator` Protocol and the shared `MATE`
sentinel. `ance.eval.material` provides `MaterialEval`/`NaiveEval`, the
bootstrap evaluators that prove the seam in Plan 01-03. Plan 01-04 adds
`ance.eval.tables`/`ance.eval.handcrafted` for the real Simplified
Evaluation Function-based eval.
"""

from __future__ import annotations
