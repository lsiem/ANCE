"""The `Evaluator` Protocol -- THE swap seam (D-00a, EVAL-01).

This is the single contract a future NNUE evaluator must satisfy to replace
the handcrafted eval with zero changes on the search side
(`ance/search/negamax.py` depends only on this Protocol, never a concrete
evaluator class -- see that module's docstring and
`tests/test_eval_seam.py::test_negamax_module_never_imports_a_concrete_evaluator`
for the structural proof). Per project ARCHITECTURE.md Pattern 1 / this
phase's 01-RESEARCH.md Pattern 5.
"""

from __future__ import annotations

from typing import Protocol

from ance.board.position import Position

# Shared mate-score sentinel. Reused by Phase 2/3's transposition-table
# ply-adjustment later -- picked and documented once here so every module
# that needs a mate constant imports this one rather than redefining it.
MATE = 30000


class Evaluator(Protocol):
    def evaluate(self, pos: Position) -> int:
        """Centipawns, side-to-move relative (positive = side to move is
        better). Mate is scored as ``±(MATE - ply)`` by an evaluator that
        chooses to score it itself.

        Phase 1 note: `ance/search/negamax.py` remains the sole mate scorer
        this phase -- it returns a flat ``-(MATE)``/``0`` at terminal nodes
        with no ply-adjustment, and no Phase 1 evaluator (`MaterialEval`,
        `NaiveEval`, or Plan 01-04's `HandcraftedEval`) ever exercises the
        ``±(MATE - ply)`` half of this contract. A future NNUE evaluator
        must implement mate scoring inside its own `evaluate()` if it needs
        to change this, or accept that search stays the sole mate scorer --
        a documented Phase 1 tradeoff (cross-AI review), not a gap.
        """
        ...
