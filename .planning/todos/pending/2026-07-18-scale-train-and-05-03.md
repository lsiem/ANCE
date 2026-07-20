# Next: finish scaled NNUE train + close 05-03 Elo evidence

**Created:** 2026-07-18  
**Status:** Gauntlet running (fresh scale-run net; started 2026-07-20 via /gsd-progress --next --auto)  
**Depends on:** Local scale-run artifacts (not in git — too large)

## Context

Phase 4 net was too weak / overfit (~13k train). A/B/C upgrades landed:

- **A** — trainer: AdamW+WD, cosine LR, batch 256, best-val checkpoint, early-stop, `metrics.json`
- **B** — 1M fresh SF depth-12 labeling (resumable progress)
- **C** — `ance.tools.training_dashboard` at `:8766`

**Note:** Prior ~150k labeling progress lived under the old path
`/Users/lasse/Development/Projects/ANCE` (gone) and was gitignored — this
checkout restarted labeling from 0 under `/Users/lasse/ANCE`. Resume still
works via `fresh_labels_progress.json` once present.

## Active jobs (screen)

| Session | Role |
|---------|------|
| `ance-train-dash` | Training dashboard `:8766` |
| `ance-train-scale` | Scale pipeline (label → train → export) |
| `ance-post-train` | Waits for net → install → 05-03 gauntlet → GSD close |

## Next todos (in order)

1. **Scale labeling + train** — in flight (`training.run_pipeline`, same `--out-dir`).
2. **Install new net** — automated by `post_train_close_05_03.py`.
3. **Re-run / finish 05-03 gauntlet** — ≥1000-game fixed-depth; honest `gates_failed` if Elo still bad.
4. **Close GSD 05-03** — `05-03-SUMMARY.md`, STATE/ROADMAP (also automated).

## Resume commands

```bash
# Training dashboard
.venv/bin/python -u -m ance.tools.training_dashboard \
  --serve --host 127.0.0.1 --port 8766 --open \
  --out-dir .planning/phases/04-offline-nnue-training-pipeline/scale-run

# Scale pipeline (resumes labels from progress JSON)
screen -dmS ance-train-scale bash -lc '
cd /Users/lasse/ANCE
export PYTHONUNBUFFERED=1
export PATH="/opt/homebrew/bin:$PATH"
.venv/bin/python -u -m training.run_pipeline \
  --fresh-target-positions 1000000 \
  --depth 12 \
  --max-hours 72 \
  --batch-size 256 \
  --early-stop-patience 5 \
  --epochs 50 \
  --out-dir .planning/phases/04-offline-nnue-training-pipeline/scale-run \
  >> .planning/phases/04-offline-nnue-training-pipeline/scale-run/scale-run.log 2>&1
'

# Post-train closer (net → gauntlet → SUMMARY/STATE/ROADMAP)
screen -dmS ance-post-train bash -lc '
cd /Users/lasse/ANCE
export PYTHONUNBUFFERED=1
export PATH="/opt/homebrew/bin:$PATH"
.venv/bin/python -u .planning/phases/05-nnue-swap-in-elo-gauntlet/post_train_close_05_03.py \
  >> .planning/phases/05-nnue-swap-in-elo-gauntlet/post-train-close.log 2>&1
'

# Gauntlet dashboard (after net install / during 05-03)
.venv/bin/python -u -m ance.tools.gauntlet_dashboard \
  --serve --host 127.0.0.1 --port 8765 --sf-depth 12
```

## Local artifacts (gitignored)

- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/fresh_labels_progress.json`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/training-live.json`
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json`
