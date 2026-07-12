# Phase 4: Offline NNUE Training Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 4-Offline NNUE Training Pipeline
**Areas discussed:** Data source & labeling, Compute ambition, Net size N, Export format, Training signal / K scaling

---

## Data source & labeling

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Lichess [%eval] | Parse existing SF-NNUE eval tags; fastest, skip labeling pass | |
| Fresh Stockfish labeling | Own Stockfish pass at fixed depth/nodes; full control, slower | |
| Both / hybrid | Lichess bulk + targeted Stockfish top-up, merged dataset | ✓ |

**User's choice:** Both / hybrid
**Notes:** Bulk volume from Lichess `[%eval]`, controlled coverage from fresh Stockfish; exact labeling command must be recorded (TRN-01).

---

## Compute ambition

| Option | Description | Selected |
|--------|-------------|----------|
| Validated pipeline first | Correctness-first, modest dataset, strength deferred to cloud | |
| Push for max strength now | Maximize dataset/training on M4 this milestone | ✓ |

**User's choice:** Push for max strength now
**Notes:** Conflicts with PROJECT.md compute-budget deferral; reconciled via a bounded wall-clock cap (see below).

### Compute bound (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Wall-clock cap | Size dataset/epochs to fixed ~8–12h M4 run; bounded & reproducible | ✓ |
| Dataset-size cap | Fix sample count, train to convergence regardless of time | |
| Best-effort, revisit | Modest run, measure, decide scale-up later | |

**User's choice:** Wall-clock cap (~8–12h overnight)

---

## Net size N

| Option | Description | Selected |
|--------|-------------|----------|
| N=256 | ~393k FT params; common first-net width | ✓ |
| N=128 | Smaller/faster, lighter Phase-5 inference, lower capacity | |
| Make N configurable | Parameterize N, default + easy sweep | |

**User's choice:** N=256

---

## Export format

| Option | Description | Selected |
|--------|-------------|----------|
| npz (numpy) | Plain np.savez, zero extra deps | |
| safetensors | Safe/typed/fast, JSON header, small dep on loader | ✓ |

**User's choice:** safetensors

---

## Training signal / K scaling

| Option | Description | Selected |
|--------|-------------|----------|
| Fit K empirically | argmin fit of sigmoid(cp/K) to game result, lock fitted K | ✓ |
| Fixed K≈400 | Single documented constant, no calibration | |
| Pure WDL target | Train on game outcome directly where available | |

**User's choice:** Fit K empirically
**Notes:** Resolves the standing STATE blocker on K (~360–400). Real WDL outcomes are ground truth in the fit where available.

---

## Claude's Discretion

- On-disk dataset shard format (.npy/.npz vs packed binary), DataLoader/feature-encoding internals, optimizer/LR schedule, checkpoint cadence.
- Specific Lichess dump(s) and any rating/time-control filtering on bulk ingest (subject to the wall-clock cap).

## Deferred Ideas

- Incremental accumulator (make/unmake hooks) — later optimization.
- King-bucketed/larger nets and cloud `bullet` training — future scale-up milestone.
- Reviewed but not folded: depth-4 gauntlet todo and En Croissant validation todo — both Phase 5 gameplay/measurement scope.

---

*Phase: 04-offline-nnue-training-pipeline*
*Discussion log generated: 2026-07-12*
