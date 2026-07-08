"""Slow depth-vs-depth ordering proof (D-14)."""

from __future__ import annotations

import pytest

from ance.eval.handcrafted import HandcraftedEval
from ance.tools.depth_vs_depth_match import run_depth_match


@pytest.mark.slow
def test_deeper_search_scores_at_least_fifty_percent() -> None:
    """Depth 4 vs depth 2 over 5 games — deeper side must score >= 50%.

    Measured 2026-07-08: depth-4 games ~8-10 min each; n_games=5 keeps
    the proof under ~25 min while demonstrating monotonic depth gain.
    """
    result = run_depth_match(
        shallow_depth=2,
        deep_depth=4,
        n_games=5,
        evaluator=HandcraftedEval(),
    )
    assert result["score_rate"] >= 0.5, (
        f"deeper side scored {result['score_rate']:.1%} "
        f"({result['wins']}W/{result['draws']}D/{result['losses']}L over {result['n_games']} games)"
    )
