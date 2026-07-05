"""The search package -- a minimal fixed-depth negamax substrate (D-01).

`ance.search.negamax` depends only on `ance.eval.base.Evaluator` (the
Protocol), never a concrete evaluator implementation -- that boundary is
what makes the eval seam (D-00a) a real, swappable contract rather than a
cosmetic one (project ARCHITECTURE.md Anti-Pattern 3).
"""

from __future__ import annotations
