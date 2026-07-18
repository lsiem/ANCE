```markdown
# ANCE Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns, coding conventions, and workflows used in the ANCE repository—a Python codebase focused on NNUE (Efficiently Updatable Neural Network) training and evaluation. You'll learn how to contribute new features, fix bugs, and maintain code quality in line with the project's standards.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for all Python files.  
  *Example:*  
  ```
  ance/tools/training_dashboard.py
  tests/test_nnue_accumulator.py
  ```

- **Import Style:**  
  Use relative imports within the package.  
  *Example:*  
  ```python
  from .features import NNUEFeatureExtractor
  from ..utils import load_config
  ```

- **Export Style:**  
  Use named exports—define and import specific functions or classes rather than using wildcard imports.  
  *Example:*  
  ```python
  # ance/eval/nnue/eval.py
  def evaluate_nnue(...):
      ...
  ```

- **Commit Messages:**  
  Follow the [Conventional Commits](https://www.conventionalcommits.org/) style.  
  - Prefixes: `feat`, `fix`
  - Example:  
    ```
    feat: add batch normalization to NNUE accumulator
    fix: correct feature extraction for king safety
    ```

## Workflows

### NNUE Training Feature Development
**Trigger:** When you want to add or improve NNUE training functionality or related dashboards.  
**Command:** `/new-nnue-training-feature`

1. **Modify or add NNUE training and evaluation code**  
   - Edit or create files such as `ance/eval/nnue/eval.py`, `ance/eval/nnue/features.py`, or `training/train.py`.
   - *Example:*
     ```python
     # ance/eval/nnue/features.py
     class NewFeatureExtractor:
         ...
     ```
2. **Update or add dashboard and tooling scripts**  
   - Update files like `ance/tools/gauntlet_dashboard.py` or `ance/tools/training_dashboard.py`.
3. **Update or add test files for new or changed features**  
   - Add or modify tests in `tests/test_nnue_accumulator.py` or `tests/training/test_training_dashboard_smoke.py`.
   - *Example:*
     ```python
     def test_new_feature_extractor():
         ...
     ```
4. **Update planning or documentation files**  
   - Reflect new features or next steps in `.planning/STATE.md` or `.planning/todos/pending/*.md`.

---

### NNUE Training Bugfix or Review
**Trigger:** When you need to fix issues or respond to code review in NNUE training or evaluation code.  
**Command:** `/fix-nnue-training-issue`

1. **Modify NNUE training or evaluation code to fix issues**  
   - Edit files like `ance/eval/nnue/eval.py`, `training/train.py`, or `ance/tools/gauntlet.py`.
   - *Example:*
     ```python
     # Fix accumulator bug
     def accumulate(...):
         ...
     ```
2. **Update or fix related test files**  
   - Update tests such as `tests/test_nnue_accumulator.py` or `tests/training/test_stockfish_labeler.py`.
3. **Update supporting scripts or labelers if needed**  
   - Modify files like `training/label/stockfish_labeler.py` or `training/run_pipeline.py` to ensure consistency.

---

## Testing Patterns

- **Framework:** Not explicitly specified; likely uses standard Python testing tools (e.g., `unittest` or `pytest`).
- **Test File Naming:**  
  - Test files use the pattern `test_*.py`.
  - Example: `tests/test_nnue_accumulator.py`
- **Test Structure:**  
  - Tests are written as functions or classes in dedicated files.
  - *Example:*
    ```python
    def test_accumulator_behavior():
        ...
    ```

## Commands

| Command                      | Purpose                                                      |
|------------------------------|--------------------------------------------------------------|
| /new-nnue-training-feature   | Start a new NNUE training feature or dashboard enhancement   |
| /fix-nnue-training-issue     | Fix a bug or address review comments in NNUE training code   |
```
