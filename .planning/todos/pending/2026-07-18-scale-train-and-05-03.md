# Next: finish scaled NNUE train + close 05-03 Elo evidence

**Created:** 2026-07-18  
**Updated:** 2026-07-19  
**Status:** In progress (05-03 gauntlet running on cloud)  
**Depends on:** Local scale-run artifacts (not in git — too large) OR stronger retrain

## Context

Phase 4 net was too weak / overfit (~13k train). A/B/C upgrades landed:

- **A** — trainer: AdamW+WD, cosine LR, batch 256, best-val checkpoint, early-stop, `metrics.json`
- **B** — 1M fresh SF depth-12 labeling (resumable progress) — local Mac only; not on cloud
- **C** — `ance.tools.training_dashboard` at `:8766`

Scale labeling paused at **~150k / 1,000,000** labels (Mac-local progress JSON).

### Cloud resume 2026-07-19 (`/gsd-progress --next`)

GSD routed **Route 4 → execute Phase 05** (missing `05-03-SUMMARY.md`). Safe-resume: Task 1 already committed (`bdfda2d`); Task 2 remaining.

Attempted HF-primary scale substitute:

```bash
.venv/bin/python -u -m training.run_pipeline \
  --hf-dataset Lichess/chess-position-evaluations \
  --fresh-n-games 0 \
  --hf-max-positions 250000 \
  --batch-size 256 --epochs 50 --early-stop-patience 5 \
  --max-hours 8 \
  --out-dir .planning/phases/04-offline-nnue-training-pipeline/cloud-hf-run
```

Result: train completed (`best_val_loss≈0.024`) but net failed D-14/D-16 goldens and lost 4/4 depth-3 smoke games vs handcrafted. Restored Phase-4 `run-output/net.safetensors`. Incremental NNUE parity OK.

Started durable 05-03 gauntlet (`run_gauntlet_05_03.py`, tmux `ance-gauntlet-05-03`). Early score **0–5**. Host calibration ~150 s/game → ~41 h for 1000 games.

## Next todos (in order)

1. ~~Resume scale labeling~~ / HF substitute attempted — need stronger net still.
2. ~~Start 05-03 gauntlet~~ — **RUNNING** (checkpoint resume).
3. Let ≥1000-game run finish; write `05-GAUNTLET-EVIDENCE.json` honestly (`gates_failed` if Elo still bad).
4. Write `05-03-SUMMARY.md` + sync ROADMAP/STATE; gap plan if D-12 fails (stronger train: resume SF 1M on Mac, or fix HF train quality / mate clipping).

## Resume commands

```bash
# Gauntlet (resumes checkpoint)
.venv/bin/python -u .planning/phases/05-nnue-swap-in-elo-gauntlet/run_gauntlet_05_03.py

# After gauntlet completes — slow gate writes evidence if missing
.venv/bin/python -m pytest tests/test_phase5_elo_evidence.py -m slow -x

# Mac-local scale pipeline (if continuing SF labels)
.venv/bin/python -u -m training.run_pipeline \
  --fresh-target-positions 1000000 \
  --depth 12 \
  --max-hours 72 \
  --batch-size 256 \
  --early-stop-patience 5 \
  --epochs 50 \
  --out-dir .planning/phases/04-offline-nnue-training-pipeline/scale-run
```

## Local artifacts (gitignored)

- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/fresh_labels_progress.json`
- `.planning/phases/04-offline-nnue-training-pipeline/cloud-hf-run/` (HF attempt)
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json`
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-run.log`
