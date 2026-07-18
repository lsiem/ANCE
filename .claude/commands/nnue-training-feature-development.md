---
name: nnue-training-feature-development
description: Workflow command scaffold for nnue-training-feature-development in ANCE.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /nnue-training-feature-development

Use this workflow when working on **nnue-training-feature-development** in `ANCE`.

## Goal

Implements or upgrades NNUE training features, including code changes, dashboard updates, and test coverage.

## Common Files

- `ance/eval/nnue/eval.py`
- `ance/eval/nnue/features.py`
- `ance/eval/nnue/inference.py`
- `ance/tools/gauntlet_dashboard.py`
- `ance/tools/training_dashboard.py`
- `tests/test_nnue_accumulator.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Modify or add NNUE training and evaluation code (e.g., ance/eval/nnue/*.py, training/train.py)
- Update or add dashboard and tooling scripts (e.g., ance/tools/gauntlet_dashboard.py, ance/tools/training_dashboard.py)
- Update or add test files for new or changed features (e.g., tests/test_nnue_accumulator.py, tests/training/test_training_dashboard_smoke.py)
- Update planning or documentation files to reflect new features or next steps (e.g., .planning/STATE.md, .planning/todos/pending/*.md)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.