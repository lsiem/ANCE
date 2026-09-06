# Phase 7: NNUE strength recovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-09-06
**Phase:** 7-NNUE strength recovery
**Areas discussed:** Corpus scale and source, Trainer recipe vs data-only, Acceptance and stop rules, Train and measure venue

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| 1 Corpus scale and source | Dump size / months vs HF; keep or relax quiet filter | ✓ |
| 2 Trainer recipe vs data-only | Same λ/fen-skip/AdamW vs hidden size / LR / epochs / probes | ✓ |
| 3 Acceptance and stop rules | Keep 200→1000 depth-3 vs smaller probe / early abort | ✓ |
| 4 Train and measure venue | Cloud CPU vs M4 MPS vs both; wall-clock budget | ✓ |

**User's choice:** `1,2,3,4` (all areas)
**Notes:** Default discuss mode; up to 4 questions per area.

---

## Corpus scale and source

### Q1 — Primary data direction

| Option | Description | Selected |
|--------|-------------|----------|
| Many more Lichess months, keep quiet filter | Same recipe, hundreds of thousands of quiet positions | |
| One recent large month, keep quiet filter | Current Lichess dump instead of 2013-01 | |
| Keep 2013-01, relax quiet filter | More positions from the same dump | |
| Switch primary source to Hugging Face / another labeled set | Lichess dumps as fallback | ✓ |
| Something else | User names source and size | |

**User's choice:** 4
**Notes:** Phase 6 `n_merged=19866` lost 0–200.

### Q2 — Which labeled set

| Option | Description | Selected |
|--------|-------------|----------|
| Existing ingest `Lichess/chess-position-evaluations` | Reuse `hf_ingest.py` | (via 4) |
| Same HF repo, treat primary as a much larger cap | Size next | |
| A different Hugging Face chess-eval dataset | User names repo id | |
| You decide | Lock option 1 unless planning finds a blocker | ✓ |

**User's choice:** 4 (You decide → existing ingest)

### Q3 — Source mix

| Option | Description | Selected |
|--------|-------------|----------|
| HF primary + Lichess PGN fill | Keep result-bearing dump for λ / `fit_k` | (via 4) |
| HF-only; relax `--strength-corpus` | Drop zst requirement and 50% result floor | |
| HF primary + small PGN fill, lower result floor | e.g. 10–20% `has_result` | |
| You decide | Option 1, modest PGN fill | ✓ |

**User's choice:** 4 (You decide → HF + modest PGN fill)

### Q4 — Filter and cap

| Option | Description | Selected |
|--------|-------------|----------|
| Keep quiet filter; raise the HF cap | Avoid another ~20k collapse | (via 4) |
| Drop quiet filter on HF; depth/knodes only | Full capped HF stream | |
| Keep quiet filter and default 250k cap | Smallest change | |
| You decide | Option 1; exact cap in planning | ✓ |

**User's choice:** 4 (You decide → quiet on, cap raised)

**Continue or next:** 2 Next area

---

## Trainer recipe vs data-only

### Q1 — Data-only vs retune

| Option | Description | Selected |
|--------|-------------|----------|
| Data-only | Freeze λ, skip, LR, epochs, probes | |
| Data + light recipe tune | Keep arch; allow λ / skip / LR / epoch / probe tweaks | (via 4) |
| Data + aggressive recipe | Retune several knobs + new regularizers | |
| You decide | Option 2 | ✓ |

**User's choice:** 4 (You decide → light tune, arch frozen)

### Q2 — Which knobs

| Option | Description | Selected |
|--------|-------------|----------|
| λ schedule only | Hold λ=1.0 longer or end nearer 0.5 | |
| Regularization / skip only | Fen-skip, epochs, patience | |
| Both λ and skip/epochs; leave LR/AdamW | Light tune without a new optimizer | (via 4) |
| You decide | Option 3 | ✓ |

**User's choice:** 4 (You decide → λ + skip/epochs)

### Q3 — Which net to install

| Option | Description | Selected |
|--------|-------------|----------|
| Val-loss only | Same as Phase 6 | |
| In-train Elo probes; install best-Elo if it beats best-val | Avoid another unplayable loss-min | (via 4) |
| In-train Elo probes for logging only; still best-val | | |
| You decide | Option 2 | ✓ |

**User's choice:** 4 (You decide → best-Elo vs best-val)

### Q4 — Warm-start vs scratch

| Option | Description | Selected |
|--------|-------------|----------|
| From scratch | New init on the new corpus | (via 4) |
| Fine-tune the Phase 6 net | Continue current weights | |
| Try both if budget allows | Scratch first | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → from scratch)

**Continue or next:** 2 Next area

---

## Acceptance and stop rules

### Q1 — Measurement ladder

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 200 → 1000 at depth 3 | Comparable to Phase 6 0–200 | (via 4) |
| Smaller probe, then 1000 at depth 3 | e.g. 50–100 then TOOL-04 | |
| Keep 200 → 1000 but raise search depth | Slower | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → same ladder)

### Q2 — Abort before 200

| Option | Description | Selected |
|--------|-------------|----------|
| Diagnostics only, then always probe | Phase 6 | |
| Diagnostics + tiny play smoke | Skip 200 if smoke is hopeless | (via 4) |
| Stricter static diagnostics only | e.g. startpos near 0 | |
| You decide | Option 2 | ✓ |

**User's choice:** 4 (You decide → diagnostics + smoke)

### Q3 — Failed probe disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Stop and fail honestly | No 1000, no second train | (via 4) |
| One in-phase retry | One more train if budget remains | |
| Keep iterating until budget is exhausted | | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → honest fail)

### Q4 — What counts as success

| Option | Description | Selected |
|--------|-------------|----------|
| TOOL-04 only | Pass iff 1000-game gate passes | |
| TOOL-04 is the goal; a clearly better probe is a useful fail | Still `gates_failed` if TOOL-04 misses | (via 4) |
| Redefine success as better than Phase 6 probe | TOOL-04 becomes a bonus | |
| You decide | Option 2 | ✓ |

**User's choice:** 4 (You decide → TOOL-04 pass bar; useful fail allowed)

**Continue or next:** 2 Next area

---

## Train and measure venue

### Q1 — Where to train vs measure

| Option | Description | Selected |
|--------|-------------|----------|
| Train on M4 MPS; measure on this cloud CPU | MPS for fit; same gauntlet host as Phase 6 | (via 4) |
| Do everything on this cloud CPU | Reduced cap/epochs | |
| Do everything on M4 | Cloud ships harness/docs only | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → split venue)

### Q2 — What the cloud agent must finish unaided

| Option | Description | Selected |
|--------|-------------|----------|
| Measure-only | Blocked evidence if net missing; no CPU train | (via 4) |
| Train here if no M4 net is present | Reduced-cap CPU fallback | |
| Always try a reduced CPU train, even if an M4 net exists | | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → measure-only)

### Q3 — Wall-clock caps

| Option | Description | Selected |
|--------|-------------|----------|
| M4 a few hours; cloud ~18h including 1000 if 200 passes | Same measure budget as Phase 6 | (via 4) |
| Tighter | M4 ~1–2h; cloud well under 18h | |
| Loose | Overnight M4; cloud may exceed 18h | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → few hours / ~18h)

### Q4 — How the net enters the repo

| Option | Description | Selected |
|--------|-------------|----------|
| Commit the export on this branch | Replace `ance/eval/nnue/net.safetensors` + sidecar | (via 4) |
| Keep the net out of git; closer reads a local path or env | | |
| PR the net from a separate train branch | Closer waits for merge | |
| You decide | Option 1 | ✓ |

**User's choice:** 4 (You decide → in-tree commit)

**Continue or wrap:** 2 Done with these areas

---

## Wrap-up

| Option | Description | Selected |
|--------|-------------|----------|
| Explore more gray areas | e.g. sidecar schema, exact HF cap, λ numbers | |
| I’m ready for context | Write CONTEXT + discussion log | ✓ |

**User's choice:** 2

---

## Claude's Discretion

User selected **You decide** on corpus Q2–Q4, all four recipe questions, all
four accept questions, and all four venue questions. Locked interpretations
are in `07-CONTEXT.md` D-01–D-16. Numeric knobs (HF cap, λ endpoints, smoke
size, PGN month) remain planner discretion.

## Deferred Ideas

None.
