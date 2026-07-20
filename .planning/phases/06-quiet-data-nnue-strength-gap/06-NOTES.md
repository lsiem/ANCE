# Phase 6 notes — quiet-data strength gap

## Lichess PGN dump (required for `--strength-corpus`)

Strength runs require `--lichess-zst` so ≥50% of merged rows carry `game_result`.

```bash
# Example: one month of rated standard games (large; use a smaller dump for smokes)
# https://database.lichess.org/
curl -L -o lichess_db_standard_rated_YYYY-MM.pgn.zst \
  https://database.lichess.org/standard/lichess_db_standard_rated_YYYY-MM.pgn.zst

python -m training.run_pipeline \
  --strength-corpus \
  --lichess-zst lichess_db_standard_rated_YYYY-MM.pgn.zst \
  --hf-dataset Lichess/chess-position-evaluations \
  --hf-max-positions 200000 \
  --fresh-n-games 0 \
  --depth 9 \
  --quiet-filter \
  --start-lambda 1.0 --end-lambda 0.75 \
  --random-fen-skipping 3 \
  --elo-probe-every 5 \
  --out-dir .planning/phases/06-quiet-data-nnue-strength-gap/strength-run
```

## Exit gates

1. `training/diagnostics_eval.py` on installed net
2. 200-game depth-3 probe with `elo_ci_low > 0`
3. ≥1000-game TOOL-04 (`post_train_close_06.py`)
4. Optional clock/nodes note + accumulator parity (already unit-tested)

## Active run (2026-07-20)

- tmux: `ance-strength-06`
- out: `strength-run/`
- data: `data/lichess_db_standard_rated_2013-01.pgn.zst` (~34k eval samples)
- elo probes during train: disabled (`--elo-probe-every 0`); use closer after export
