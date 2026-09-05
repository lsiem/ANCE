# Phase 06: strength retrain → post_train_close_06

**Created:** 2026-09-05  
**Status:** Strength-corpus training in flight  
**Branch:** `cursor/phase06-post-train-close-933d`

## Context

`/gsd-progress --next` on stale 05-04 branch: main already closed 05-03 (honest fail) and advanced to Phase 06. Next work is TOOL-04 re-gate via quiet/result-bearing strength run + `post_train_close_06.py`.

## In flight

```bash
# tmux ance-strength-06
.venv/bin/python -u -m training.run_pipeline \
  --strength-corpus \
  --lichess-zst .planning/phases/06-quiet-data-nnue-strength-gap/data/lichess_db_standard_rated_2013-01.pgn.zst \
  --hf-dataset Lichess/chess-position-evaluations --hf-max-positions 200000 \
  --fresh-n-games 0 --quiet-filter \
  --start-lambda 1.0 --end-lambda 0.75 --random-fen-skipping 3 \
  --elo-probe-every 0 --epochs 50 --out-dir .planning/phases/06-quiet-data-nnue-strength-gap/strength-run
```

## Next

1. Wait for `strength-run/net.safetensors`
2. `python -u .planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py`
3. Commit `06-GAUNTLET-EVIDENCE.json` + SUMMARY; sync ROADMAP/STATE
