# Phase 7 User Setup — M4 from-scratch train (blocked on this host)

**Status:** Incomplete
**Service:** apple-silicon-m4
**Why:** D-13 trains on M4 MPS. This cloud Linux host is CPU-only (`torch.backends.mps.is_available()` → False, `2.14.0+cpu`). D-14 forbids a reduced CPU train. Plan 07-04 will write blocked evidence until this sitting lands.

Do **not** run `training.run_pipeline` on the cloud Linux host.
Do **not** write a fake `07-NET-SIDECAR.json` (that would make 07-04 measure the Phase 6 net).
Do **not** overwrite `ance/eval/nnue/net.safetensors` until a real from-scratch M4 export exists.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| (none) | — | No extra env vars. Use the PROJECT M4 venv with native arm64 Python 3.12. |
| `PYTORCH_ENABLE_MPS_FALLBACK` | optional | Set to `1` on M4 if unimplemented ops appear. NNUE is Linear + ClippedReLU. |

## Account / machine checklist

- [ ] PROJECT Apple Silicon M4 Mac (24 GB unified memory), native arm64 Python — not Rosetta
- [ ] `python -c "import torch; assert torch.backends.mps.is_available()"` exits 0
- [ ] `pip install -e '.[hf-ingest]'` if `huggingface_hub` / `pyarrow` missing
- [ ] Stockfish via `brew install stockfish` (quiet capture-bestmove)
- [ ] Working tree includes Plan 07-01 (`--lichess-max-samples` and 4-field FEN pad)
- [ ] Lichess 2013-01 dump present: `lichess_db_standard_rated_2013-01.pgn.zst`

## Dashboard / local config

| Task | Location |
|------|----------|
| Install extras and Stockfish, then run the pinned CLI after 07-01 lands | PROJECT M4 Mac with `pip install -e '.[hf-ingest]'` and brew Stockfish |

## M4 sitting steps

1. Confirm MPS:

   ```bash
   python -c "import torch; assert torch.backends.mps.is_available()"
   ```

2. Confirm extras:

   ```bash
   pip install -e '.[hf-ingest]'
   ```

3. Confirm Lichess 2013-01 dump sha256
   `aa40b3671fa3cf1072eb182892cd90b0e1e003a4a5943492f64b77e7f3fd1635`
   (re-check `https://database.lichess.org/standard/sha256sums.txt` before curl).

4. Run the exact CLI (also `M4_PIPELINE_ARGV` in
   `.planning/phases/07-nnue-strength-recovery/install_phase7_net.py`).
   Do **not** pass `--resume-from-checkpoint` (D-08).
   Do **not** change AdamW / LR flags (D-06).

   ```bash
   python -m training.run_pipeline \
     --strength-corpus \
     --quiet-filter \
     --lichess-zst lichess_db_standard_rated_2013-01.pgn.zst \
     --lichess-max-samples 80000 \
     --hf-dataset Lichess/chess-position-evaluations \
     --hf-max-positions 750000 \
     --hf-min-depth 20 \
     --hf-min-knodes 1000 \
     --fresh-n-games 0 \
     --min-has-result-rate 0.15 \
     --max-fresh-share 0.10 \
     --start-lambda 1.0 \
     --end-lambda 0.75 \
     --random-fen-skipping 2 \
     --epochs 30 \
     --early-stop-patience 6 \
     --batch-size 256 \
     --lr 1e-3 \
     --weight-decay 1e-4 \
     --elo-probe-every 5 \
     --elo-probe-games 12 \
     --max-hours 5 \
     --out-dir .planning/phases/07-nnue-strength-recovery/strength-run
   ```

5. If the first in-train probe exceeds 25 minutes, drop remaining probes to 8 games (still D-07).
   If kept HF after quiet is under 30000, stop honestly — do not start a second train (D-11).

6. After export, install the from-scratch net and write the sidecar:

   ```bash
   python .planning/phases/07-nnue-strength-recovery/install_phase7_net.py \
     --src .planning/phases/07-nnue-strength-recovery/strength-run/best_elo.safetensors \
     --meta /path/to/run-meta.json
   ```

   Prefer `best_elo.safetensors` when it exists; otherwise the best-val export.
   `run-meta.json` should supply `n_merged`, `has_result_rate`, `best_elo`,
   `best_elo_epoch`, `best_val_loss`, `k_scale`, `installed_utc`.
   `write_sidecar` always locks `phase=7`, `from_scratch=true`, and copies
   `arch_id` / `feature_set` from `nnue_format.schema` (D-05 keep-768x2-256-1).

7. Commit `ance/eval/nnue/net.safetensors` +
   `.planning/phases/07-nnue-strength-recovery/07-NET-SIDECAR.json` on the
   working branch (D-16). Push so the cloud closer can see them.

## Verification

On the M4 after install:

```bash
python -c "import json; d=json.load(open('.planning/phases/07-nnue-strength-recovery/07-NET-SIDECAR.json')); assert d['phase']==7 and d['from_scratch'] is True"
```

On this cloud host (current blocked resume):

```bash
python -c "import torch; print(torch.backends.mps.is_available())"   # must print False
test ! -f .planning/phases/07-nnue-strength-recovery/07-NET-SIDECAR.json
```

## Local notes

- Architecture stays `768x2-256-1` / `board768`. Do not change hidden width or feature-set.
- This file stays Status Incomplete until the M4 sitting commits net + sidecar.
- Plan 07-04 is allowed to write blocked evidence while this setup is Incomplete.
