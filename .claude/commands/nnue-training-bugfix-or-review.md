---
name: nnue-training-bugfix-or-review
description: Workflow command scaffold for nnue-training-bugfix-or-review in ANCE.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /nnue-training-bugfix-or-review

Use this workflow when working on **nnue-training-bugfix-or-review** in `ANCE`.

## Goal

Addresses bugs or PR review comments in NNUE training and related paths, ensuring code and tests are updated together.

## Common Files

- `ance/eval/nnue/eval.py`
- `ance/tools/gauntlet.py`
- `tests/test_nnue_accumulator.py`
- `tests/training/test_stockfish_labeler.py`
- `training/label/stockfish_labeler.py`
- `training/run_pipeline.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Modify NNUE training or evaluation code to fix issues (e.g., ance/eval/nnue/eval.py, training/train.py)
- Update or fix related test files (e.g., tests/test_nnue_accumulator.py, tests/training/test_stockfish_labeler.py)
- Update supporting scripts or labelers if needed (e.g., training/label/stockfish_labeler.py, training/run_pipeline.py)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.