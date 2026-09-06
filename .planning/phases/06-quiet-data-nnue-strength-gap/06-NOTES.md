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

## Active run (2026-09-05)

- Branch: `cursor/phase06-quiet-data-closer-0af2`
- Net: installed `ance/eval/nnue/net.safetensors` (quiet-data, `n_merged=19866`, epoch 18, K≈451)
- Closer: `post_train_close_06.py` (diagnostics polarity-only; probe budget 18h)
- Prior train: Lichess 2013-01 quiet corpus; no `strength-run/` dir in this checkout (net already copied into the engine package)
- Probe live: 121/200 after ~5.1 h, NNUE 0–121 (score 0.0), ~141 s/game → ~3.1 h remaining
