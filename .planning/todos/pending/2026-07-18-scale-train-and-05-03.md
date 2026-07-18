# Next: finish scaled NNUE train + close 05-03 Elo evidence

**Created:** 2026-07-18  
**Status:** Paused (user stop)  
**Depends on:** Local scale-run artifacts (not in git — too large)

## Context

Phase 4 net was too weak / overfit (~13k train). A/B/C upgrades landed:

- **A** — trainer: AdamW+WD, cosine LR, batch 256, best-val checkpoint, early-stop, `metrics.json`
- **B** — 1M fresh SF depth-12 labeling (resumable progress)
- **C** — `ance.tools.training_dashboard` at `:8766`

Scale labeling paused at **~150k / 1,000,000** labels.

## Next todos (in order)

1. **Resume scale labeling** — `screen` / `training.run_pipeline` with same `--out-dir` (uses `fresh_labels_progress.json`).
2. **Finish train + export** — wait for shards → train (early-stop) → `net.safetensors` in scale-run.
3. **Install new net** — copy/export into `ance/eval/nnue/` (replace weak Phase 4 weights).
4. **Re-run / finish 05-03 gauntlet** — ≥1000-game fixed-depth NNUE vs handcrafted; write `05-GAUNTLET-EVIDENCE.json` honestly (`gates_failed` if Elo still bad).
5. **Close GSD 05-03** — `05-03-SUMMARY.md`, STATE/ROADMAP, phase verify (gap plan if D-12 fails).

## Resume commands

```bash
# Training dashboard
.venv/bin/python -u -m ance.tools.training_dashboard \
  --serve --host 127.0.0.1 --port 8766 \
  --out-dir .planning/phases/04-offline-nnue-training-pipeline/scale-run

# Scale pipeline (resumes labels from progress JSON)
screen -dmS ance-train-scale bash -lc '
cd /Users/lasse/Development/Projects/ANCE
export PYTHONUNBUFFERED=1
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

# Gauntlet dashboard (if resuming 05-03)
.venv/bin/python -u -m ance.tools.gauntlet_dashboard \
  --serve --host 127.0.0.1 --port 8765 --sf-depth 12
```

## Local artifacts (gitignored)

- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/fresh_labels_progress.json`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/training-live.json`
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json`
