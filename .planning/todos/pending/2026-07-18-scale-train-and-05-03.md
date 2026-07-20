# Next: close 05-03 Elo evidence with HF-trained net

**Created:** 2026-07-18  
**Updated:** 2026-07-19  
**Status:** Train+export done (cloud HF-primary); gauntlet remaining  
**Depends on:** Installed `ance/eval/nnue/net.safetensors` from scale-run export

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
- Exported + installed `ance/eval/nnue/net.safetensors`

## Next todos (in order)

1. ~~Resume scale labeling~~ — skipped in cloud; used HF pre-labeled stream instead.
2. ~~Finish train + export~~ — done (`scale-run/net.safetensors` + metrics/manifest).
3. ~~Install new net~~ — copied into `ance/eval/nnue/net.safetensors`.
4. **Re-run / finish 05-03 gauntlet** — ≥1000-game fixed-depth NNUE vs handcrafted; write `05-GAUNTLET-EVIDENCE.json` honestly (`gates_failed` if Elo still bad).
5. **Close GSD 05-03** — `05-03-SUMMARY.md`, STATE/ROADMAP, phase verify (gap plan if D-12 fails).

## Optional follow-ups

- Larger HF stream (more shards / higher `--hf-max-positions`) — first-shard ingest collides heavily on FEN; 250k → ~37k unique.
- Resume Mac SF 1M labeling if local `fresh_labels_progress.json` still exists (separate out-dir to avoid clobbering HF artifacts).

## Resume commands

```bash
# Training dashboard
.venv/bin/python -u -m ance.tools.training_dashboard \
  --serve --host 127.0.0.1 --port 8766 \
  --out-dir .planning/phases/04-offline-nnue-training-pipeline/scale-run

# Gauntlet dashboard (resume 05-03)
.venv/bin/python -u -m ance.tools.gauntlet_dashboard \
  --serve --host 127.0.0.1 --port 8765 --sf-depth 12
```

## Local artifacts (gitignored)

- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/hf_samples.json`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/merged_samples.json`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/{train,val}.npz`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/checkpoints/`
- `.planning/phases/04-offline-nnue-training-pipeline/scale-run/net.safetensors`
- `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json`
