# Next: close 05-03 Elo evidence with HF-trained net

**Created:** 2026-07-18  
**Updated:** 2026-07-20  
**Status:** Superseded — 05-03 closed with honest `gates_failed`; Phase 6 strength-run next  
**Depends on:** —

## Context

Phase 4 net was too weak / overfit (~13k train). A/B/C upgrades landed:

- **A** — trainer: AdamW+WD, cosine LR, batch 256, best-val checkpoint, early-stop, `metrics.json`
- **B** — 1M fresh SF depth-12 labeling (local Mac progress was gitignored; not available in cloud)
- **C** — `ance.tools.training_dashboard` at `:8766`
- **HF path** — `Lichess/chess-position-evaluations` ingest (PR #4) used for cloud resume

### Cloud training run (2026-07-19)

- Mode: `--fresh-n-games 0 --hf-dataset Lichess/chess-position-evaluations --hf-max-positions 250000`
- Device: CPU (Linux cloud; no MPS/Stockfish)
- Ingested 250k HF rows → **36,755** unique after FEN dedup → 34,855 train / 1,900 val
- Trained 50 epochs; best val loss **0.02422** @ epoch 50; `K=400` fallback
- Exported + installed `ance/eval/nnue/net.safetensors` (later superseded by local scale-run / Phase 6 nets)

### Local scale-run (2026-07-20)

- Completed early-stop @ epoch 49; metrics committed under `scale-run/metrics.json`
- 05-03 evidence written with `gates_failed` (TOOL-04 not met)

### Phase 6 (current)

- Quiet-data harness + Lichess 2013-01 strength-run trained
- Net installed from `strength-run/net.safetensors`
- **Next:** `post_train_close_06.py` (200-game probe → ≥1000 TOOL-04)

## Todos (historical — closed)

1. ~~Resume scale labeling / train+export / install net~~ — done
2. ~~05-03 gauntlet evidence~~ — committed; `gates_failed` honest
3. ~~05-03 SUMMARY + STATE/ROADMAP~~ — done; Phase 6 opened

## Active next

```bash
# Phase 6 closer (diagnostics → 200 probe → ≥1000 TOOL-04)
python3 -u .planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py \
  >> .planning/phases/06-quiet-data-nnue-strength-gap/post-train-close.log 2>&1
```

## Local artifacts (gitignored)

- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/hf_samples.json`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/merged_samples.json`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/{train,val}.npz`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/checkpoints/`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/net.safetensors`
- `.planning/phases/06-quiet-data-nnue-strength-gap/data/`
- `.planning/phases/06-quiet-data-nnue-strength-gap/strength-run/` (except committed snapshots)
