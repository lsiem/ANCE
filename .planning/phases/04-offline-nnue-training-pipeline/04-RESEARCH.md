# Phase 4: Offline NNUE Training Pipeline - Research

**Researched:** 2026-07-13
**Domain:** Offline supervised NNUE training (PyTorch/MPS) — Stockfish/Lichess labeling, dataset construction, `(768→256)×2→1` net, safetensors export
**Confidence:** MEDIUM-HIGH (architecture/quantization spec and package registry facts are HIGH; the exact MPS-on-this-machine outcome and Stockfish labeling throughput are unverified until the first training-harness task runs — this is intentional per D-09, not a research gap)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Data source & labeling**
- **D-01:** Hybrid position/label source. Bootstrap bulk volume from existing Lichess `[%eval]` tags (SF-NNUE @ ~40 Mnodes, ~6% of games in the open-database `.pgn.zst` dumps), then top up with a fresh Stockfish labeling pass over a targeted position set for controlled depth/coverage. The two streams merge into one deduplicated dataset.
- **D-02:** The fresh-labeling pass MUST record the exact Stockfish UCI command (fixed depth/nodes) and use normalized UCI cp output — never internal eval (TRN-01). Planning/research must pin the depth-or-nodes value.
- **D-03:** Dedup by FEN; split by game so no FEN leaks across train/val, with an automated assertion that the split is disjoint (TRN-02). Lichess-sourced samples carry their originating game id so the by-game split applies to them too.

**Training signal & scaling**
- **D-04:** Target = sigmoid-scaled win probability. The scaling constant K is fit empirically — choose K minimizing the fit between `sigmoid(cp/K)` and the observed game result over the dataset, then lock and record the fitted K. This resolves the standing STATE blocker (previously "~360–400 must be pinned").
- **D-05:** Where a real game WDL outcome is available (Lichess games), it is the ground-truth result used in the K fit; cp→sigmoid is the target where only an eval exists.

**Net architecture sizing**
- **D-06:** Hidden width N = 256 → `(768→256)×2→1` (~393k feature-transformer params). Fixed for this milestone. (Bigger/king-bucketed nets deferred to cloud scale-up per PROJECT.md.)

**Export format**
- **D-07:** Export via safetensors with a JSON header carrying `arch_id`, `feature_set_id`, and tensor shapes. The engine-side loader in `nnue_format/` validates these and roundtrips with zero torch dependency (numpy-only read).

**Compute ambition & bound**
- **D-08:** Ambition is max strength within a bounded M4 run — NOT the "modest first net" default. Planning sizes dataset + epochs to a fixed wall-clock cap (~8–12h, an overnight run) on the M4, pushing strength as far as that budget allows while keeping the run finite and reproducible. This is the agreed reconciliation with PROJECT.md's "heavy runs deferred to cloud" — the cloud/NVIDIA path remains the route for anything beyond this bounded run.

**MPS safety (locked direction, first task)**
- **D-09:** The very first training-harness task is an MPS gate: `torch.backends.mps.is_available()` smoke test + a float32 CPU-vs-MPS numeric parity check on one forward/backward step (TRN-05). CPU training is an accepted fallback for this tiny net if MPS is unavailable/regressed on the target macOS. float32 throughout — no float64, no AMP/FP16 (MPS constraints).

### Claude's Discretion
- Concrete dataset schema on disk (`.npy`/`.npz` shards vs packed binary of encoded 768-feature indices + label) — planner/researcher choose per throughput.
- DataLoader/feature-encoding implementation details, checkpoint cadence, optimizer (Adam default) and LR schedule — standard approaches unless research says otherwise.
- Which specific Lichess dump(s) and any time-control/rating filtering on the bulk ingest, subject to the wall-clock cap in D-08.

### Deferred Ideas (OUT OF SCOPE)
- Incremental accumulator (make/unmake feature-delta hooks) — later optimization, not required for this phase's full-recompute training/export.
- King-bucketed / larger nets, cloud/NVIDIA `bullet` training — deferred to a future scale-up milestone per PROJECT.md; the ~8–12h M4 cap (D-08) is the ceiling here.
- `2026-07-07-tool-02-depth-4-gauntlet-deferred.md` — belongs to Phase 5.
- `2026-07-08-phase2-encroissant-validation.md` — validation/measurement task tied to gameplay phases, not offline training.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRN-01 | A Stockfish labeling pipeline produces (FEN → centipawn) training samples at a fixed depth/nodes, using normalized UCI cp output (not internal eval) | §Standard Stack (Stockfish/python-chess), §Code Examples (labeler using `SimpleEngine.analyse` + `info["score"].relative`), §Common Pitfalls #2 (normalized-cp confirmation) |
| TRN-02 | A dataset is generated with a train/validation split held out by game (not by position) to prevent leakage | §Architecture Patterns Pattern 2 (by-game split + FEN dedup), §Validation Architecture (no-overlap assertion) |
| TRN-03 | The `(768→N)×2→1` NNUE trains in PyTorch on the MPS backend against a sigmoid-scaled win-probability target | §Architecture Patterns Pattern 1 (net + forward pass), §Architecture Patterns Pattern 4 (K-fit + loss), §Code Examples |
| TRN-04 | Trained weights export to a plain format (npz/safetensors) and the running engine loads them at startup | §Architecture Patterns Pattern 5 (`nnue_format` contract), §Code Examples (safetensors numpy round-trip) — loader itself is produced here; engine load-at-startup wiring is Phase 5 |
| TRN-05 | Training verifies MPS availability and runs a float32 CPU-vs-MPS numeric sanity check before the real run | §Common Pitfalls #1 (macOS 26 Tahoe MPS regression — confirmed present on THIS machine), §Environment Availability, §Code Examples (MPS gate script) |
</phase_requirements>

## Summary

This phase is a two-stream ETL pipeline (Lichess `[%eval]` reuse + fresh Stockfish labeling) feeding a small, well-specified `(768→256)×2→1` PyTorch net, trained on MPS-or-CPU-fallback against a sigmoid-win-probability target, exported through a zero-torch `nnue_format` contract. Every piece of this is well-trodden ground (`official-stockfish/nnue-pytorch` is the canonical reference architecture and loss function), so the real risk in this phase is not "what to build" but three concrete correctness traps documented in `.planning/research/PITFALLS.md` and reconfirmed here: (1) **MPS availability on this exact machine is currently broken** — this development Mac reports macOS 26.5.2 (Tahoe), which is precisely the macOS major flagged in open PyTorch issues (#167679, #177819) where `mps.is_built()==True` but `mps.is_available()==False` on PyTorch 2.9.1/2.10/2.12-nightly; D-09's CPU fallback is not a hypothetical hedge, it is the **likely primary path** for this run and must be planned as such, not as an edge case; (2) Lichess `[%eval]` annotations are **White-relative**, not side-to-move-relative — every value pulled from the bulk stream must be sign-flipped when it's Black to move, or the dataset silently corrupts labels (this is Pitfall 10's "NNUE killer bug" applied to data ingestion, not just feature construction); (3) the K-fit (D-04) has a well-known, tool-supported method (`scipy.optimize.curve_fit` / logistic regression of `sigmoid(cp/K)` against observed game result, the same approach as `official-stockfish/WDL_model`) — this is not a research gap, it is a concrete, scriptable calibration step that must run on the merged dataset before training and whose output (`K`) gets written into both the training logs and the exported weights metadata.

**Primary recommendation:** Build `training/` as a torch-only top-level (never imported by `ance/`), sequence the plan as MPS-gate → labeler → ingest/merge/dedup/split → K-fit calibration → `(768→256)×2→1` train loop → safetensors export via `nnue_format`, and treat every stage as an independently-resumable artifact-producing step (dataset manifest → labeled samples → merged/split shards → fitted K → checkpoint → exported net) so an interrupted 8–12h overnight run loses at most one stage's work.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Stockfish fresh labeling (TRN-01) | Offline Training — Labeling (`training/label/`) | — | Drives an external Stockfish subprocess via `chess.engine`; pure offline I/O, never touches the running engine |
| Lichess bulk ingestion (D-01) | Offline Training — Data (`training/data/ingest`) | — | Streaming-decompress + PGN-parse an external corpus; no runtime coupling |
| Dataset merge/dedup/split (TRN-02, D-03) | Offline Training — Data (`training/data/`) | — | Pure data-engineering stage; produces the shards the model tier consumes |
| K calibration (D-04, D-05) | Offline Training — Data/Calibration | Offline Training — Training (writes into checkpoint metadata) | Statistical fit over the merged dataset; its output (K) is consumed by both the loss function (Training tier) and the exported weights metadata (Export tier) |
| Model definition + MPS/CPU train loop (TRN-03, TRN-05) | Offline Training — Training (`training/model.py`, `training/train.py`) | — | The only tier that imports torch; strictly isolated from `ance/` |
| Weights export (TRN-04, D-07) | Shared Contract (`nnue_format/`) | Offline Training — Export (`training/export.py` calls into the contract) | `nnue_format/` is imported by both this phase's `export.py` and Phase 5's engine-side loader — it is the physical embodiment of the training→engine boundary and must stay torch-free itself |
| Engine load-at-startup (part of TRN-04's full text) | Online Engine Runtime (`ance/eval/nnue/`) | — | **Out of this phase's scope** — Phase 5 builds `NnueEval`; this phase only produces a weights file the *future* loader can validate. Listed for traceability only. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyTorch | 2.13.0 latest stable (2.9.0+ acceptable; verify MPS on install — see Pitfall #1) [VERIFIED: PyPI registry, `pip index versions torch`] | Train the `(768→256)×2→1` net | Already the project's committed training framework (PROJECT.md/STACK.md); MPS ships in normal wheels |
| NumPy | 2.5.1 latest [VERIFIED: PyPI registry] | Feature-index encoding, dataset shard math, zero-torch safetensors read-back | Already committed; also the substrate for the eventual (Phase 5) numpy-only inference path this export must support |
| `chess` (python-chess) | 1.11.2 (already installed in project `.venv`) [VERIFIED: installed + PyPI registry] | Drive Stockfish over UCI (`chess.engine`) for fresh labeling; FEN/board parsing for feature extraction | Already the project's board library; `chess.engine.SimpleEngine` is the documented way to script an external UCI engine |
| `safetensors` | 0.8.0 latest [VERIFIED: PyPI registry, `pip index versions safetensors`] | Export format (D-07) | `safetensors.numpy.save_file`/`load_file` give exactly the "zero torch dependency" round-trip D-07 requires — this is a first-class supported framework in the library, not a workaround [CITED: huggingface.co/docs/safetensors/api/numpy] |
| `zstandard` | 0.25.0 latest [VERIFIED: PyPI registry, `pip index versions zstandard`] | Streaming-decompress Lichess `.pgn.zst` monthly dumps | `ZstdDecompressor().stream_reader(fh)` gives a file-like object usable directly with `chess.pgn.read_game()` without buffering the whole (tens-of-GB) file in memory |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tqdm` | 4.68.4 latest [VERIFIED: PyPI registry] | Progress bars for labeling pass and training loop | Any stage that runs unattended for hours — visible progress matters for the 8–12h cap |
| `scipy` | latest (`optimize.curve_fit`) — not previously in the project stack; new for this phase | Fit K in D-04 via nonlinear least squares of `sigmoid(cp/K)` against observed game result | The standard tool for exactly this fit; `official-stockfish/WDL_model` uses the same class of fit for Stockfish's own WDL calibration [CITED: github.com/official-stockfish/WDL_model] |
| `pytest` | 8.x (already in project) | Test the dataset split-disjointness assertion, MPS-gate script, safetensors round-trip | Consistent with the rest of the project's test suite |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `scipy.optimize.curve_fit` for K-fit | Hand-rolled gradient descent on the sigmoid | scipy is a two-line, well-tested fit; hand-rolling risks a silent local-minimum/convergence bug in a calibration constant that gets baked into the whole training run — don't hand-roll this |
| `safetensors` for export | Plain `numpy.savez` | Both satisfy "zero torch dependency"; safetensors adds a typed JSON header (arch id/shapes) as a first-class feature and is the format D-07 already locked in — use it as specified, `.npz` is the documented fallback only if safetensors has an installation problem |
| PyTorch MPS | MLX | Already rejected in STACK.md for this project (smaller NNUE precedent, non-portable weights); re-litigating this is out of scope — CPU fallback (per D-09) is the correct hedge, not a framework switch |
| Fresh Stockfish labeling for 100% of data | Lichess `[%eval]` only | D-01 already locks the hybrid; pure-Lichess would skip labeling entirely but caps coverage/depth control — the hybrid is the decision, not a discretion point |

**Installation:**
```bash
# New for this phase (torch/numpy/chess already present per PROJECT.md decisions)
pip install torch safetensors zstandard tqdm scipy
python -c "import torch; print(torch.__version__, torch.backends.mps.is_available(), torch.backends.mps.is_built())"
```

**Version verification performed this session:**
```
$ pip index versions torch        -> 2.13.0 (2.9.0–2.13.0 all listed)
$ pip index versions numpy        -> 2.5.1
$ pip index versions safetensors  -> 0.8.0
$ pip index versions zstandard    -> 0.25.0
$ pip index versions tqdm         -> 4.68.4
$ pip index versions chess        -> 1.11.2 (already installed)
```
None of torch/numpy/safetensors/zstandard/scipy/tqdm are currently installed in this project's `.venv` — this phase's first task must install them.

## Package Legitimacy Audit

> The `gsd-tools query package-legitimacy check` seam was unavailable in this installed gsd-tools version (`Unknown command: package-legitimacy`) — see Sources for the manual-verification substitute used instead: direct PyPI registry history (`pip index versions`, which lists every published release back to each package's first version) plus official-documentation cross-check. This is a documented deviation from the standard protocol, not a skipped step.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| torch | PyPI | ~9 yrs (first release 2017; 2.13.0 current) | very high (tens of millions/week, industry-standard) | github.com/pytorch/pytorch | OK | Approved — already a locked project dependency (PROJECT.md) |
| numpy | PyPI | ~19 yrs (1.3.0 in 2008 visible in history; now 2.5.1) | very high | github.com/numpy/numpy | OK | Approved — already a locked project dependency |
| chess | PyPI | ~10 yrs (1.0.0 era visible; now 1.11.2) | high (de-facto Python chess library) | github.com/niklasf/python-chess | OK | Approved — already installed and in use |
| safetensors | PyPI | ~3 yrs (0.0.1 through 0.8.0 continuous releases) | high — HuggingFace's standard tensor-serialization format, widely depended on across the ML ecosystem [ASSUMED: exact download figure not queried this session] | github.com/huggingface/safetensors | OK | Approved — new dependency this phase, satisfies D-07 exactly |
| zstandard (python-zstandard) | PyPI | ~10 yrs (0.1 through 0.25.0 continuous releases) | moderate-high [ASSUMED: exact download figure not queried this session] | github.com/indygreg/python-zstandard | OK | Approved — new dependency this phase |
| scipy | PyPI | ~15+ yrs, foundational SciPy stack | very high | github.com/scipy/scipy | OK | Approved — new dependency this phase, used only for `optimize.curve_fit` |
| tqdm | PyPI | ~11 yrs (versions from 1.0 through 4.68.4) | very high | github.com/tqdm/tqdm | OK | Approved — already recommended in STACK.md |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none. All packages in this table are long-lived, widely-used, and were cross-checked against official documentation (PyTorch docs, HuggingFace safetensors docs, python-chess readthedocs, python-zstandard readthedocs) rather than relying on WebSearch alone for their existence — the planner does not need to insert a `checkpoint:human-verify` before these installs, but should still note in the task that the automated legitimacy seam was substituted this session.

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────── PHASE 4 SCOPE: OFFLINE TRAINING (torch, never shipped) ───────────────────────────┐
│                                                                                                                │
│  Lichess .pgn.zst dump          targeted position set                                                        │
│  (bulk, [%eval] tags)           (fresh labeling)                                                              │
│         │                                │                                                                    │
│         ▼                                ▼                                                                    │
│  ┌───────────────────┐          ┌───────────────────────┐                                                     │
│  │ zstd stream reader │          │ Stockfish labeler      │  chess.engine.SimpleEngine, fixed depth/nodes,    │
│  │ + PGN game parser   │          │ (training/label/)      │  reads info["score"].relative (normalized cp)     │
│  │ extract [%eval],    │          │ records exact UCI cmd  │                                                     │
│  │ game result, game id│          └───────────┬───────────┘                                                     │
│  └─────────┬───────────┘                      │                                                                │
│            │ (fen, cp_or_mate, game_result, game_id)   (fen, cp, game_id=synthetic)                            │
│            └──────────────────┬───────────────┘                                                                │
│                                ▼                                                                                │
│                    ┌────────────────────────────┐                                                              │
│                    │ Merge + dedup by FEN         │  keep first/highest-confidence label per FEN               │
│                    │ (training/data/merge.py)     │                                                              │
│                    └──────────────┬─────────────┘                                                              │
│                                   ▼                                                                             │
│                    ┌────────────────────────────┐                                                              │
│                    │ Split by game_id (D-03)      │  assert train ∩ val FEN sets == ∅ (automated check)        │
│                    └──────────────┬─────────────┘                                                              │
│                                   ▼                                                                             │
│                    ┌────────────────────────────┐                                                              │
│                    │ K-fit calibration (D-04/05)  │  scipy.optimize.curve_fit(sigmoid(cp/K), game_result)      │
│                    │ over train split; lock K      │  writes K into run manifest + (later) weights metadata    │
│                    └──────────────┬─────────────┘                                                              │
│                                   ▼                                                                             │
│                    ┌────────────────────────────┐        ┌───────────────────────────┐                        │
│                    │ Feature-encode to 768-index │───────▶│ MPS gate (D-09, FIRST TASK)│  mps.is_available()   │
│                    │ shards (training/data/)      │        │ CPU-vs-MPS parity check    │  fallback to CPU      │
│                    └──────────────┬─────────────┘        └─────────────┬─────────────┘                        │
│                                   ▼                                    ▼                                       │
│                    ┌───────────────────────────────────────────────────────────┐                              │
│                    │ (768→256)×2→1 PyTorch model + train loop (training/train.py)│                             │
│                    │ float32 only; sigmoid(cp/K) target blended w/ game result   │                             │
│                    │ checkpoints every N steps; val loss tracked (Nyquist gate)  │                             │
│                    └───────────────────────────┬─────────────────────────────────┘                            │
│                                                 ▼                                                                │
│                    ┌───────────────────────────────────────────────────────────┐                              │
│                    │ export.py: state_dict → nnue_format.save_net(arrays, meta)  │                             │
│                    └───────────────────────────┬─────────────────────────────────┘                            │
└─────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┘
                                                    ▼
                              ┌───────────────────────────────────────┐
                              │  nnue_format/  (SHARED, zero torch)    │  ◀── THE HANDOFF CONTRACT (D-07)
                              │  schema.py: arch_id, feature_set,      │
                              │             shapes, output_scale, K    │
                              │  io.py: save_net() / load_net()        │      validates + fails loudly
                              │  net.safetensors + JSON header         │      on shape/id mismatch
                              └───────────────────┬─────────────────────┘
                                                    │ consumed by (OUT OF SCOPE — Phase 5)
                                                    ▼
                              ┌───────────────────────────────────────┐
                              │  ance/eval/nnue/  NnueEval (numpy)     │  Phase 5
                              └───────────────────────────────────────┘
```

### Recommended Project Structure

```
training/                        # OFFLINE — torch-only top-level, never imported by ance/
├── label/
│   ├── stockfish_labeler.py     # chess.engine.SimpleEngine driver, fixed depth/nodes, records exact command
│   └── position_source.py       # generates/loads the targeted FEN set for fresh labeling
├── data/
│   ├── lichess_ingest.py        # zstd stream + chess.pgn parse, extract [%eval]/result/game_id, sign-fix to STM
│   ├── merge.py                 # merge Lichess + fresh streams, dedup by FEN
│   ├── split.py                 # by-game train/val split + disjoint-FEN assertion
│   ├── kfit.py                  # D-04 calibration: scipy.optimize.curve_fit over train split, writes K
│   ├── features.py              # position -> 768 active-feature indices (mirrors ance/eval/nnue/features.py spec)
│   └── shards.py                # on-disk shard format (packed binary or .npy — Claude's discretion), DataLoader
├── model.py                      # (768->256)x2->1 in torch: FeatureTransformer + ClippedReLU + output layer
├── mps_gate.py                   # D-09: is_available() + is_built() + CPU-vs-MPS float32 parity check — FIRST RUN
├── train.py                      # train loop: device selection (mps|cpu), sigmoid-K loss, val loss, checkpoints
├── export.py                     # torch state_dict -> nnue_format.save_net(arrays, meta incl. K, arch_id, ...)
└── run_manifest.py               # records: labeling command(s), dataset manifest hashes, seeds, fitted K, git sha

nnue_format/                      # SHARED — imported by training/ AND (Phase 5) ance/eval/nnue/ — zero torch
├── schema.py                     # arch_id="768x2-256-1", feature_set="board768", shapes, output_scale, K field
└── io.py                         # save_net(...)/load_net(...) — numpy-only; validates arch/feature-set/shapes

tests/
└── training/                     # kept separate so the main ance/ suite never needs torch installed
    ├── conftest.py                # skip collection if torch unavailable (pytest.importorskip("torch"))
    ├── test_mps_gate.py
    ├── test_split_no_leakage.py
    ├── test_kfit_calibration.py
    └── test_nnue_format_roundtrip.py   # this one CAN run without torch — numpy-only save/load
```

### Structure Rationale (extends ARCHITECTURE.md)

- `training/` matches the layout already fixed in `.planning/research/ARCHITECTURE.md` §Recommended Project Structure; this research adds the concrete submodule breakdown (`label/`, `data/{lichess_ingest,merge,split,kfit,features,shards}.py`) needed to plan tasks against.
- `mps_gate.py` is its own module, not folded into `train.py`, so it can be run and tested independently as the D-09 "first task" and imported by `train.py` for device selection without duplicating logic.
- `tests/training/` is separated from the main `tests/` suite (not interleaved) specifically so the existing torch-free `ance/` test suite (24 plans' worth of tests) keeps working with no new dependency, per the "never shipped into the engine runtime" rule extended to test collection.
- `run_manifest.py` exists because D-08's reproducibility requirement ("fixed seeds, recorded dataset manifest, recorded labeling command, recorded fitted K") is itself a deliverable, not an afterthought — give it a home.

### Pattern 1: The `(768→256)×2→1` net and forward pass (nnue-pytorch canonical spec)

**What:** A single shared feature transformer (768 inputs → 256 hidden) run twice — once from the side-to-move's perspective, once from the opponent's — concatenated `[stm_acc, opp_acc]` (512-wide), ClippedReLU, then a single linear layer to one scalar output.
**When to use:** This is D-06's locked architecture; not a choice point.
**Source:** `official-stockfish/nnue-pytorch/docs/nnue.md` [CITED: github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md] — "the net can learn tempo" by concatenating the side-to-move accumulator first, then the opponent's.

```python
# training/model.py — Source: nnue-pytorch/docs/nnue.md architecture, adapted to N=256 (D-06)
import torch
import torch.nn as nn

NUM_FEATURES = 768   # 64 squares x 6 piece types x 2 colors
HIDDEN = 256          # D-06

class ClippedReLU(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.clamp(x, 0.0, 1.0)   # float [0,1]; quantized net later maps to [0,127] (deferred, PITFALLS #13)

class NNUE(nn.Module):
    def __init__(self, num_features: int = NUM_FEATURES, hidden: int = HIDDEN) -> None:
        super().__init__()
        self.ft = nn.Linear(num_features, hidden)          # shared feature transformer
        self.clipped_relu = ClippedReLU()
        self.output = nn.Linear(hidden * 2, 1)               # x2: two-perspective concat

    def forward(self, stm_features: torch.Tensor, opp_features: torch.Tensor) -> torch.Tensor:
        stm_acc = self.clipped_relu(self.ft(stm_features))
        opp_acc = self.clipped_relu(self.ft(opp_features))
        combined = torch.cat([stm_acc, opp_acc], dim=1)      # [stm, opp] order -- learns tempo
        return self.output(combined).squeeze(-1)              # raw scalar; scale to cp at inference
```

`stm_features`/`opp_features` are each a `[batch, 768]` float32 tensor built from the position's active-feature indices (sparse, ~30 active per side) — encode as dense float32 for a first-cut DataLoader (simplicity over speed; this is training-time only and the net is tiny) or as sparse index lists if throughput demands it (Claude's discretion, per CONTEXT.md).

### Pattern 2: By-game split with automated disjointness assertion (TRN-02, D-03, Pitfall #12)

**What:** Every FEN is tagged with its originating `game_id` (real Lichess game id, or a synthetic id per fresh-labeling batch); the split operates on `game_id`, never on individual FENs.
**When to use:** Always, for every source stream (Pitfall #12 — position-level splits leak near-duplicate/transposed positions across train/val and silently invalidate the val loss).

```python
# training/data/split.py — Source: PITFALLS.md Pitfall 12 + nnue-pytorch data hygiene practice
import random

def split_by_game(samples: list[dict], val_fraction: float = 0.05, seed: int = 42) -> tuple[list[dict], list[dict]]:
    game_ids = sorted({s["game_id"] for s in samples})       # sorted -> deterministic before shuffle
    rng = random.Random(seed)
    rng.shuffle(game_ids)
    cut = int(len(game_ids) * (1 - val_fraction))
    train_ids, val_ids = set(game_ids[:cut]), set(game_ids[cut:])
    train = [s for s in samples if s["game_id"] in train_ids]
    val = [s for s in samples if s["game_id"] in val_ids]
    return train, val

def assert_no_fen_leakage(train: list[dict], val: list[dict]) -> None:
    train_fens = {s["fen"] for s in train}
    val_fens = {s["fen"] for s in val}
    overlap = train_fens & val_fens
    assert not overlap, f"{len(overlap)} FENs leaked across train/val split (TRN-02 violation)"
```

### Pattern 3: K-fit calibration (D-04, D-05) via nonlinear least squares

**What:** Fit the scalar `K` in `sigmoid(cp/K)` to best match observed game outcomes (0/0.5/1 for loss/draw/win, STM-relative), using every sample that has a real game result (the Lichess stream, per D-05); fresh-Stockfish-only samples (no game attached) are excluded from the *fit* but still trained on afterward with the fitted K.
**When to use:** Once, after merge+split, before training; run on the **train** split only (the val split must stay untouched by any fitting step, same leakage discipline as the net itself).
**Source:** Method mirrors `official-stockfish/WDL_model`'s WDL-fit approach [CITED: github.com/official-stockfish/WDL_model] and the `nnue-pytorch` loss's own `sigmoid(eval/scaling)` convention, scaling constant commonly ~400 [CITED: nnue-pytorch/docs/nnue.md — "Stockfish uses values around 400"].

```python
# training/data/kfit.py
import numpy as np
from scipy.optimize import curve_fit

def sigmoid(cp: np.ndarray, k: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-cp / k))

def fit_k(cp_values: np.ndarray, game_results: np.ndarray, k0: float = 400.0) -> float:
    """cp_values: STM-relative centipawns for samples that have a real game_result
    (0.0/0.5/1.0, STM-relative). Returns the fitted K (lock this into the run manifest
    and the exported weights metadata, per D-04)."""
    (k_fit,), _ = curve_fit(sigmoid, cp_values, game_results, p0=[k0])
    return float(k_fit)
```

Rationale for excluding samples with no real result from the *fit* input: fitting K against `sigmoid(cp/K)` compared to *itself* (a Stockfish-eval-only sample has no independent ground truth) is circular and would trivially converge without informing anything — D-05 already specifies this ("cp→sigmoid is the target where only an eval exists", i.e., not part of the K-fit's supervision signal).

### Pattern 4: Sigmoid-WDL training loss (TRN-03) with the fitted K

**What:** `nnue-pytorch`'s MSE-in-WDL-space loss, parameterized by the fitted K, blending eval-derived target and real game result per D-05.
**Source:** `nnue-pytorch/docs/nnue.md` — `wdl_value_target = lambda_ * wdl_eval_target + (1 - lambda_) * game_result`; `loss = (wdl_eval_model - wdl_value_target)**2` [CITED].

```python
# training/train.py (loss fragment) — Source: nnue-pytorch/docs/nnue.md, K from kfit.py
import torch

def wdl_loss(model_out_cp: torch.Tensor, eval_cp: torch.Tensor,
             game_result: torch.Tensor, has_result: torch.Tensor,
             k: float, lambda_: float = 0.5) -> torch.Tensor:
    wdl_model = torch.sigmoid(model_out_cp / k)
    wdl_eval_target = torch.sigmoid(eval_cp / k)
    # D-05: where a real result exists, blend; where it doesn't, target is pure eval (lambda_=1 for those rows)
    effective_lambda = torch.where(has_result.bool(), torch.full_like(eval_cp, lambda_), torch.ones_like(eval_cp))
    target = effective_lambda * wdl_eval_target + (1 - effective_lambda) * game_result
    return ((wdl_model - target) ** 2).mean()
```

### Pattern 5: `nnue_format` contract (D-07) — safetensors + zero-torch numpy read

**What:** `training/export.py` converts the trained `state_dict` to plain float32 numpy arrays and calls `nnue_format.save_net`; the format module's `load_net` (usable with zero torch installed, per D-07 and the earlier ARCHITECTURE.md contract) validates `arch_id`/`feature_set`/shapes and fails loudly on mismatch.
**Source:** `safetensors.numpy.save_file`/`load_file` are first-class numpy bindings in the library [CITED: huggingface.co/docs/safetensors/api/numpy].

```python
# nnue_format/io.py
from safetensors.numpy import save_file, load_file
import json
import numpy as np

ARCH_ID = "768x2-256-1"
FEATURE_SET = "board768"

def save_net(arrays: dict[str, np.ndarray], meta: dict[str, str], path: str) -> None:
    # meta values must be strings per safetensors header convention; JSON-encode structured fields
    header_meta = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in meta.items()}
    save_file({k: v.astype(np.float32) for k, v in arrays.items()}, path, metadata=header_meta)

def load_net(path: str) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    from safetensors import safe_open
    with safe_open(path, framework="numpy") as f:
        meta = f.metadata() or {}
        arrays = {key: f.get_tensor(key) for key in f.keys()}
    if meta.get("arch_id") != ARCH_ID:
        raise ValueError(f"arch_id mismatch: expected {ARCH_ID}, got {meta.get('arch_id')}")
    if meta.get("feature_set") != FEATURE_SET:
        raise ValueError(f"feature_set mismatch: expected {FEATURE_SET}, got {meta.get('feature_set')}")
    expected_shapes = {"ft.weight": (768, 256), "ft.bias": (256,), "out.weight": (512, 1), "out.bias": (1,)}
    for name, shape in expected_shapes.items():
        if name in arrays and tuple(arrays[name].shape) != shape:
            raise ValueError(f"{name} shape mismatch: expected {shape}, got {arrays[name].shape}")
    return arrays, meta
```

`meta` must include (D-04, D-08 reproducibility): `k_scale` (fitted K), `arch_id`, `feature_set`, `format_version`, `output_scale`, and ideally the labeling command + dataset manifest hash for provenance.

### Anti-Patterns to Avoid

- **Treating Lichess `[%eval]` as already STM-relative:** it is White-relative in the PGN annotation [CITED: lichess.org forum + database docs]. Flip the sign for every sample where the position-to-move is Black before it enters the merged dataset — do this once in `lichess_ingest.py`, not scattered across later stages.
- **Fitting K against Stockfish-eval-only samples:** circular (Pattern 3) — only fit against samples with a real, independent game result.
- **Running the K-fit or any calibration step against the val split:** violates the same leakage discipline TRN-02 enforces for the net itself; the val split must remain untouched until final evaluation.
- **Assuming `torch.backends.mps.is_available() == True` without running it on this machine first:** this development machine is macOS 26.5.2 — the exact major flagged in open PyTorch MPS regressions. Treat CPU-fallback as the expected first-run outcome, not a rare edge case (see Pitfall #1 below).
- **Loading a `.pt`/pickle checkpoint with `torch.load` from anything but your own just-written file:** pickle deserialization risk (also flagged in PITFALLS.md) — irrelevant for the shipped `nnue_format` artifact (which is safetensors, not pickle) but relevant for any intermediate training checkpoints; use `weights_only=True` if `torch.load` is used for checkpoints at all.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| K-scaling constant fit | A custom gradient-descent loop on the sigmoid | `scipy.optimize.curve_fit` | Well-tested nonlinear least squares; a hand-rolled fit risks silent non-convergence in a constant that gets baked into every subsequent training run and the exported weights metadata |
| Zero-torch weights serialization | A bespoke binary format + manual struct packing | `safetensors.numpy.save_file`/`load_file` (or `numpy.savez` as documented fallback) | D-07 already locked this in; safetensors gives a typed JSON header for free and is a maintained, security-conscious format (no pickle) |
| Streaming decompression of multi-GB `.pgn.zst` | Manual chunked-read + custom decompression buffering | `zstandard.ZstdDecompressor().stream_reader(fh)` | File-like object drops straight into `chess.pgn.read_game()`; hand-rolling risks either OOM (buffering the whole file) or subtle truncation bugs |
| UCI move/score parsing from Stockfish | Regex-parsing raw UCI protocol lines | `chess.engine.SimpleEngine.analyse()` + `info["score"]` (`PovScore`) | python-chess already parses `info depth ... score cp ...` / `score mate ...` into typed `Cp`/`Mate` objects with `.relative`/`.white()`/`.black()` conversion — this is exactly the "normalized UCI cp, never internal eval" requirement (TRN-01) satisfied by using the library as intended |
| Train/val split logic | Ad-hoc random row sampling | By-game split (Pattern 2) | Position-level random splits are the single most common NNUE data-leakage bug (Pitfall #12); this is not a place to improvise |

**Key insight:** Every "don't hand-roll" item above corresponds to a documented pitfall class (data leakage, sign errors, pickle risk, streaming OOM) that this specific project's own PITFALLS.md already flags — the libraries exist precisely because these are easy to get subtly wrong in ways that "the loss still goes down" (Pitfall #10's framing) and only surface as a weak or wrong net much later.

## Common Pitfalls

### Pitfall 1: MPS reports built-but-unavailable on macOS 26 (Tahoe) — confirmed present on this development machine

**What goes wrong:** `torch.backends.mps.is_built()` returns `True` while `torch.backends.mps.is_available()` returns `False`, with an error like "The MPS backend is supported on macOS 14.0+" even though the installed macOS (26.x) is newer than 14.0 — a version-detection regression, not an actual hardware/OS incompatibility.
**Why it happens:** Open, unresolved PyTorch issues confirm this on PyTorch 2.9.1 (stable) and 2.10.0/2.12.0.dev nightlies on macOS 26.0 and 26.3.1 [VERIFIED via WebFetch of github.com/pytorch/pytorch/issues/167679 and #177819 — issues remain open/triaged with no confirmed fix version as of this research].
**This machine specifically:** `sw_vers` on the development Mac reports `ProductVersion: 26.5.2` — squarely in the affected range. **This means D-09's "CPU training is an accepted fallback" is very likely the actual execution path for this phase's real training run, not a defensive-only branch.** The plan should budget wall-clock time (D-08's 8–12h cap) assuming CPU may be the outcome, and the MPS-gate task's exit behavior (log + continue on CPU vs. abort) needs to be decided explicitly, not left implicit.
**How to avoid:** Task 1 of the plan (D-09) must run `python -c "import torch; print(torch.__version__, torch.backends.mps.is_available(), torch.backends.mps.is_built())"` on the actual machine as its first action, before anything else is built. If unavailable, try the latest stable PyTorch release (2.13.0) and the latest nightly as a quick check (regression fixes sometimes land in nightlies before the next stable), but do not block the phase on a fix landing — proceed on `device="cpu"` per D-09's explicit acceptance of that fallback.
**Warning signs:** `is_built()==True` and `is_available()==False` together (the specific broken combination, not just "False/False" which would mean no Metal support at all).

### Pitfall 2: Normalized UCI cp vs internal Stockfish eval (TRN-01's exact wording)

**What goes wrong:** Since Stockfish 12, the UCI `info score cp` output is a *normalized* value (roughly, 100cp ≈ 50% win probability at LTC) — a deliberately different number from Stockfish's internal NNUE evaluation. Mixing the two (e.g., reading internal eval via a debug/tools path, or an older Stockfish that hasn't normalized yet) corrupts the labeling target's scale.
**Why it happens:** Both numbers are called "the eval" colloquially; only one of them is what actually comes over the wire via UCI `info` lines.
**How to avoid:** Drive Stockfish only through `chess.engine.SimpleEngine.analyse()` and read `info["score"]` — this is exactly the UCI-reported (normalized) value, already parsed into a `PovScore` by python-chess [VERIFIED via WebFetch of python-chess readthedocs engine docs]. `info["score"].relative` is STM-relative (matches the project's `Evaluator` convention and this dataset's target convention) without any extra conversion. Use a current Stockfish (17.1 or 18, per STACK.md) so the normalization is in effect.
**Warning signs:** Label values wildly out of the ordinary ±2000cp range for balanced middlegame positions, or label magnitudes that don't roughly track known evaluations of the same FENs from lichess.org's own analysis board.

### Pitfall 3: Lichess `[%eval]` is White-relative, not side-to-move-relative

**What goes wrong:** The PGN comment `[%eval 2.35]` or `[%eval #-4]` is always given from White's point of view [VERIFIED via WebSearch of lichess.org forum + database.lichess.org documentation]. If this is ingested directly as a training label without sign-correction for Black-to-move positions, roughly half the bulk-sourced dataset has an inverted sign — the exact "NNUE killer bug" class from PITFALLS.md Pitfall #10, but injected at the data layer instead of the feature-construction layer.
**Why it happens:** It is easy to assume "the eval in the PGN" is already in the same convention the rest of the pipeline uses (STM-relative), since Stockfish's own UCI `info score` output *is* STM-relative and it's tempting to treat all "eval" numbers the same way.
**How to avoid:** In `lichess_ingest.py`, flip the sign of every parsed `[%eval]` (and mate score) when the position's side to move is Black, immediately at ingestion — before merge, before K-fit, before anything else touches the value. Add a targeted test: parse a known `[%eval]`-annotated game where Black is to move at some ply, assert the ingested label matches `-1 × the raw PGN value`.
**Warning signs:** Training loss looks fine but the net's sign contract disagrees with Stockfish's own sign on sample FENs (same detection method PITFALLS.md already prescribes for Pitfall #10) — if this shows up, check the Lichess ingestion path first, not just feature construction.

### Pitfall 4: K-fit circularity — fitting the scaling constant against unlabeled-by-outcome samples

**What goes wrong:** Including Stockfish-eval-only samples (no real game attached) in the K-fit's supervision target makes the fit trivial/circular — you'd be fitting `sigmoid(cp/K)` to compare against a target derived from the same `cp`, which converges to whatever K makes the two sides equal for no informative reason.
**Why it happens:** It's tempting to "use all the data" for calibration since more data usually helps — but this specific fit needs *independent* ground truth (real game outcomes), which only the Lichess stream provides (D-05).
**How to avoid:** Filter to `has_result == True` rows before calling `curve_fit` (Pattern 3); the fresh-Stockfish-only rows get labeled with the fitted K afterward but never participate in fitting it.
**Warning signs:** The fitted K comes back suspiciously close to whatever seed/initial guess (`p0`) was passed, or the fit "succeeds" with near-zero residual — a sign the target and the input were not actually independent.

### Pitfall 5: Train/val leakage via position-level (not game-level) splitting

Already covered exhaustively in `.planning/research/PITFALLS.md` Pitfall #12 and restated here because it is directly load-bearing for TRN-02/D-03: **split by `game_id`, dedup by FEN before splitting, and write an automated assertion (Pattern 2) that the intersection of train/val FEN sets is empty.** This is one of the five items already called out as a required checklist item in that file — treat the assertion as a blocking test, not a nice-to-have.

### Pitfall 6: Unattended 8–12h run with no resumability

**What goes wrong:** A single long-running script that holds all state in memory and writes only a final artifact loses the *entire* overnight run to any interruption (OOM per PITFALLS.md #14, a laptop sleep, an MPS kernel bug producing silently-wrong numbers partway through).
**Why it happens:** D-08's ambition ("max strength within a bounded run") tempts a single big script rather than staged, checkpointed artifacts.
**How to avoid:** Make every stage in the pipeline diagram (label → ingest → merge → split → K-fit → train → export) write its own artifact to disk and be independently re-runnable/skippable if its artifact already exists (a manifest/hash check, not just a file-exists check, to catch stale artifacts after a code change). Checkpoint the training loop itself at a fixed cadence (every N steps or every M minutes, Claude's discretion) with enough state to resume mid-epoch, given the multi-hour budget.
**Warning signs:** A crash 6 hours into an 8-hour run that requires restarting from FEN-labeling.

## Code Examples

### MPS gate (D-09, first training-harness task)

```python
# training/mps_gate.py — Source: PROJECT.md MPS constraints + PITFALLS.md Pitfall 14, adapted with the
# macOS-26-specific is_built/is_available split confirmed via github.com/pytorch/pytorch/issues/167679
import torch

def select_device() -> str:
    built = torch.backends.mps.is_built()
    available = torch.backends.mps.is_available()
    print(f"torch={torch.__version__} mps.is_built={built} mps.is_available={available}")
    if built and not available:
        print("WARNING: MPS built but unavailable -- known regression on some macOS majors "
              "(see github.com/pytorch/pytorch/issues/167679, #177819). Falling back to CPU per D-09.")
    return "mps" if available else "cpu"

def cpu_vs_mps_parity_check(device: str, atol: float = 1e-4) -> None:
    """Run one forward+backward step on both CPU and `device`, float32 only,
    fixed seed, and assert the resulting loss/gradients match within `atol`."""
    if device == "cpu":
        print("Device is CPU; parity check is a no-op (nothing to compare against).")
        return
    torch.manual_seed(0)
    from training.model import NNUE
    x1 = torch.randn(4, 768)
    x2 = torch.randn(4, 768)
    y = torch.randn(4)

    def one_step(dev: str) -> torch.Tensor:
        torch.manual_seed(0)
        model = NNUE().to(dev)
        out = model(x1.to(dev), x2.to(dev))
        loss = ((out - y.to(dev)) ** 2).mean()
        loss.backward()
        return loss.detach().cpu()

    cpu_loss = one_step("cpu")
    mps_loss = one_step(device)
    assert torch.allclose(cpu_loss, mps_loss, atol=atol), (
        f"CPU/MPS numeric mismatch: {cpu_loss.item()} vs {mps_loss.item()} "
        "-- suspect an MPS kernel bug (PITFALLS.md #14); do not trust MPS for the real run"
    )
    print(f"CPU/MPS parity OK: {cpu_loss.item():.6f} vs {mps_loss.item():.6f}")
```

### Stockfish fresh-labeling with the exact command recorded (TRN-01, D-02)

```python
# training/label/stockfish_labeler.py
import chess
import chess.engine

def label_position(engine: chess.engine.SimpleEngine, fen: str, depth: int) -> dict:
    board = chess.Board(fen)
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].relative   # STM-relative, matches ance/eval/base.py's Evaluator convention
    if score.is_mate():
        return {"fen": fen, "mate": score.mate(), "cp": None}
    return {"fen": fen, "mate": None, "cp": score.score()}

def run_labeling(stockfish_path: str, fens: list[str], depth: int) -> list[dict]:
    exact_command = f"{stockfish_path} (UCI, analyse depth={depth}, via chess.engine.SimpleEngine)"
    print(f"Labeling command (record in run_manifest.py): {exact_command}")
    with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
        return [label_position(engine, fen, depth) for fen in fens]
```

### Lichess `[%eval]` ingestion with sign correction (D-01, Pitfall #3)

```python
# training/data/lichess_ingest.py
import chess
import chess.pgn
import zstandard

def iter_games(zst_path: str):
    dctx = zstandard.ZstdDecompressor()
    with open(zst_path, "rb") as fh, dctx.stream_reader(fh) as reader:
        import io
        text_stream = io.TextIOWrapper(reader, encoding="utf-8")
        while (game := chess.pgn.read_game(text_stream)) is not None:
            yield game

def extract_samples(game: chess.pgn.Game, game_id: str) -> list[dict]:
    result_map = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}
    game_result_white = result_map.get(game.headers.get("Result", ""))
    samples = []
    board = game.board()
    for node in game.mainline():
        board.push(node.move)
        comment_eval = node.eval()  # python-chess parses [%eval ...] into a PovScore, White-relative in Lichess PGNs
        if comment_eval is None or game_result_white is None:
            continue
        stm_is_white = board.turn == chess.WHITE
        cp = comment_eval.white().score(mate_score=100000)
        if not stm_is_white:
            cp = -cp   # Pitfall #3: [%eval] is White-relative; flip for STM convention
        game_result_stm = game_result_white if stm_is_white else (1.0 - game_result_white)
        samples.append({"fen": board.fen(), "cp": cp, "game_result": game_result_stm,
                         "game_id": game_id, "source": "lichess"})
    return samples
```

### safetensors zero-torch round-trip test (validates D-07/TRN-04's contract without training a real net)

```python
# tests/training/test_nnue_format_roundtrip.py — runs WITHOUT torch installed
import numpy as np
from nnue_format.io import save_net, load_net, ARCH_ID, FEATURE_SET

def test_roundtrip_zero_torch(tmp_path):
    arrays = {
        "ft.weight": np.random.randn(768, 256).astype(np.float32),
        "ft.bias": np.zeros(256, dtype=np.float32),
        "out.weight": np.random.randn(512, 1).astype(np.float32),
        "out.bias": np.zeros(1, dtype=np.float32),
    }
    meta = {"arch_id": ARCH_ID, "feature_set": FEATURE_SET, "k_scale": "402.7", "format_version": "1"}
    path = tmp_path / "net.safetensors"
    save_net(arrays, meta, str(path))
    loaded_arrays, loaded_meta = load_net(str(path))
    for key, arr in arrays.items():
        assert np.allclose(arr, loaded_arrays[key])
    assert loaded_meta["arch_id"] == ARCH_ID
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Train NNUE with raw centipawn MSE regression | Sigmoid-WDL target blended with real game result via lambda interpolation | Standard in `nnue-pytorch` since its inception; not a recent change, but a common first-cut mistake | Raw-cp MSE destabilizes training on mate-scored outliers and mismatches how the net will be interpreted at inference; the WDL-space loss is what D-04's K-fit feeds into |
| Treat Stockfish UCI `score cp` as the raw internal evaluation | Treat it as normalized (SF12+) — a deliberately different number from internal eval | Stockfish commit `ad2aa8c` (normalization), SF12 era | Labeling pipelines built against pre-normalization assumptions produce a mis-scaled dataset; TRN-01's explicit "normalized UCI cp, not internal eval" wording exists because of this exact history |
| Assume `torch.backends.mps.is_available()` reliably reflects hardware capability | Treat it as a value that must be checked per PyTorch-version/macOS-major combination, with known regressions on macOS 26 | Ongoing — issues #167679/#177819 opened within roughly the last year and remain unresolved as of this research | D-09's gate-first-task requirement is not boilerplate caution; it is currently the load-bearing decision for whether this phase trains on GPU or CPU |

**Deprecated/outdated:**
- Large bucketed NNUE architectures (HalfKP/HalfKAv2, king buckets) are explicitly out of scope for this milestone (REQUIREMENTS.md "Out of Scope" table) — do not let research or planning drift toward them; D-06 locks the plain `(768→256)×2→1` shape.
- AMP/FP16 mixed precision on MPS: negligible benefit for this net class on M4 (already established in PROJECT.md/STACK.md) — do not reach for it even if the CPU fallback path (Pitfall #1) makes training feel slow.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A fresh-labeling depth of roughly 12–14 (or an equivalent node budget) is a reasonable starting point for balancing label quality against per-position latency on this M4, driving Stockfish single-threaded via `chess.engine` | Not yet in a table — see Open Questions #1 | If the actual achievable positions/sec at that depth is far lower than assumed, the fresh-labeling stream's contribution to the 8–12h budget (D-08) shrinks and the planner must lean more heavily on the Lichess bulk stream; recommend a short benchmark task before committing dataset size, not a guess baked into the plan |
| A2 | Approximate download-volume/popularity figures given for `safetensors` and `zstandard` in the Package Legitimacy Audit (described qualitatively as "high"/"moderate-high") | Package Legitimacy Audit | Low risk — the legitimacy verdict itself rests on verified registry history + official docs, not the download estimate; the estimate is descriptive color only |
| A3 | `scipy` was not previously part of this project's dependency set (STACK.md); adding it for the K-fit alone is the right call rather than hand-rolling scipy-free | §Standard Stack, §Don't Hand-Roll | Low risk — `curve_fit` is a single well-understood call; if `scipy` install friction ever appears, a hand-rolled Newton step on the 1-parameter sigmoid fit is a small, well-defined fallback (unlike most "don't hand-roll" items here) |
| A4 | A val_fraction around 5% (used in the Pattern 2 code example) is a reasonable default split ratio | §Architecture Patterns Pattern 2 | Low risk — this is a parameter, not a structural decision; the planner/implementer can tune it without touching the split *mechanism* (by-game, disjoint-FEN-asserted) |

**If this table is empty:** N/A — see entries above. Everything else in this document (MPS regression on macOS 26, Lichess `[%eval]` sign convention, safetensors numpy API, K~400 prior, python-chess `PovScore` semantics, package registry versions) was verified this session via WebFetch/WebSearch against primary sources or via direct tool invocation (`pip index versions`, `sw_vers`, local `.venv` introspection) — see Sources.

## Open Questions

1. **Actual Stockfish labeling throughput on this M4 (depth/nodes value to pin, D-02)**
   - What we know: Stockfish is not currently installed on this machine (`brew install stockfish` returns "not found"); PROJECT.md/STACK.md recommend Stockfish 17.1/18 via Homebrew. Modern single-threaded Stockfish at depth ~12-16 typically labels on the order of low-hundreds to a few thousand positions/minute on comparable Apple Silicon hardware, but this project has no verified figure yet [ASSUMED — training-knowledge estimate, not measured on this machine].
   - What's unclear: The exact positions/second this specific M4 achieves at a candidate depth, which determines how large a "targeted position set" (D-01) is achievable within the D-08 wall-clock budget.
   - Recommendation: The plan's first data-pipeline task should be "install Stockfish, run a 200-position timed benchmark at 2-3 candidate depths (e.g. 10, 14, 18), pick the depth/nodes value that fits the time budget for the intended fresh-labeling volume, and record the result plus the exact command" — turning this open question into a concrete, cheap, five-minute calibration task rather than a guess locked into the plan text.

2. **Which Lichess dump(s) and filtering (Claude's discretion per CONTEXT.md, but sizing matters for D-08)**
   - What we know: `database.lichess.org` publishes monthly `.pgn.zst` dumps; roughly 6% of games carry `[%eval]` annotations [CITED via WebSearch]. A recent single month is on the order of tens of GB compressed and tens of millions of games; 6% eval coverage still yields a very large raw sample count before any filtering.
   - What's unclear: The exact filesize/game-count for any specific month (not queried this session — would require fetching `database.lichess.org/standard/list.txt` at plan time), and whether rating/time-control filtering is needed to keep ingestion time inside the wall-clock budget once the actual per-game parse rate is measured.
   - Recommendation: Pick one recent month; stream-parse with an early-exit sample cap (e.g., stop after N eval-tagged positions extracted) rather than committing to processing the entire file — this bounds ingestion time regardless of the exact file size, and keeps D-08's budget protected without needing the exact figure now. This machine has 1.5TB free disk, so storage is not the constraint — wall-clock parse time is.

3. **Checkpoint cadence and DataLoader shard format (both explicitly Claude's Discretion in CONTEXT.md)**
   - What we know: The project defers this choice explicitly; either packed-binary 768-feature-index shards or `.npy`/`.npz` are viable, per PROJECT.md's own note that "the bottleneck is data pipeline throughput... not GPU memory."
   - What's unclear: Without a measured DataLoader throughput number on this hardware, it isn't possible to say definitively whether sparse-index encoding or dense-float32-768 encoding is faster in practice for this dataset size.
   - Recommendation: Start with the simpler dense-float32 `.npy` shard format (Pattern 1's code example assumes this) for a working end-to-end pipeline first; only move to packed sparse-index encoding if a measured DataLoader throughput bottleneck appears during the actual overnight run's early minutes (visible via `tqdm` epoch-time reporting). This is consistent with D-08's own framing — push for max strength within the budget, but the budget is protected by not over-engineering the shard format before there's a measured need.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (arm64) | Entire pipeline | ✓ | 3.13.14 (venv, arm64 confirmed) | — |
| `chess` (python-chess) | Labeling, board/feature encoding | ✓ | 1.11.2 (installed) | — |
| `torch` | TRN-03, TRN-05 | ✗ | — (2.13.0 latest on PyPI) | Install as first task; no viable fallback framework (MLX rejected in STACK.md) |
| `numpy` | Feature encoding, safetensors numpy read | ✗ | — (2.5.1 latest on PyPI) | Install as first task |
| `safetensors` | TRN-04/D-07 export | ✗ | — (0.8.0 latest on PyPI) | Install as first task; `numpy.savez` is the documented fallback format if safetensors install ever fails |
| `zstandard` | Lichess `.pgn.zst` ingestion | ✗ | — (0.25.0 latest on PyPI) | Install as first task; CLI `zstd` (if present) could pre-decompress to a temp file as a fallback, trading disk space (1.5TB free, not a constraint) for avoiding the library |
| `scipy` | K-fit (D-04) | ✗ | — (latest on PyPI, not previously pinned in project) | Install as first task; hand-rolled 1-parameter Newton fit is a narrow, well-defined fallback if scipy install ever has friction |
| Stockfish binary | TRN-01 fresh labeling | ✗ | — (17.1/18 per STACK.md; `brew install stockfish`) | None viable — TRN-01 requires it; install as an early task, benchmark depth/throughput immediately after (Open Question #1) |
| MPS backend (macOS/PyTorch combo) | TRN-05, faster TRN-03 | **Likely ✗ on this machine** | macOS 26.5.2 confirmed (`sw_vers`); PyTorch not yet installed to test directly | **CPU training (explicitly accepted by D-09)** — plan the wall-clock budget assuming this fallback is the real outcome, not a rare edge case |
| Disk space | Dataset shards, Lichess dump | ✓ | 1.5 TB free on the data volume | — |

**Missing dependencies with no fallback:**
- Stockfish binary — TRN-01 has no substitute; must be installed (`brew install stockfish`) before the fresh-labeling stream can run at all.

**Missing dependencies with fallback:**
- `torch`/`numpy`/`safetensors`/`zstandard`/`scipy` — all installable via `pip install`; no blocking risk, just sequencing (install-first task).
- MPS backend — CPU fallback is a first-class, already-decided (D-09) path, not a workaround improvised at execution time.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (already configured via `pyproject.toml [tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` (existing); recommend adding a `torch: requires torch (deselect with -m 'not torch')` marker alongside the existing `slow` marker, OR isolating training tests under `tests/training/` with a `conftest.py` that calls `pytest.importorskip("torch")` at collection time so the main `ance/` suite (currently torch-free) is never forced to install torch to run |
| Quick run command | `pytest tests/training/ -x -q` (once `tests/training/` exists) |
| Full suite command | `pytest tests/ tests/training/ -q` (existing suite + new training suite) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRN-01 | Stockfish labeler produces (FEN→cp) at fixed depth using normalized UCI cp, exact command recorded | integration (requires `stockfish` binary; skip if absent) | `pytest tests/training/test_stockfish_labeler.py -x` | ❌ Wave 0 |
| TRN-02 | Dataset split by game, no FEN appears in both train/val | unit | `pytest tests/training/test_split_no_leakage.py -x` | ❌ Wave 0 |
| TRN-03 | Net trains on MPS-or-CPU against sigmoid-WDL target with decreasing val loss | integration/smoke (short run, few steps, synthetic data) | `pytest tests/training/test_train_loop_smoke.py -x` | ❌ Wave 0 |
| TRN-04 | Exported weights roundtrip with zero torch, validated arch/shapes | unit (numpy-only, no torch needed) | `pytest tests/training/test_nnue_format_roundtrip.py -x` | ❌ Wave 0 |
| TRN-05 | MPS gate: is_available() check + float32 CPU-vs-MPS numeric parity | unit/smoke (skips parity math gracefully if MPS unavailable, per Pitfall #1) | `pytest tests/training/test_mps_gate.py -x` | ❌ Wave 0 |
| D-04 (K-fit correctness) | `curve_fit` recovers a known K from synthetic sigmoid-generated data within tolerance | unit | `pytest tests/training/test_kfit_calibration.py -x` | ❌ Wave 0 |
| D-01/Pitfall #3 (Lichess sign correction) | `[%eval]` White-relative value flips correctly for Black-to-move samples | unit | `pytest tests/training/test_lichess_ingest_sign.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/training/ -x -q` (fast unit tests; the Stockfish-integration and train-loop-smoke tests should each run in well under 30s using tiny synthetic/fixture data, not the real multi-hour pipeline)
- **Per wave merge:** `pytest tests/ tests/training/ -q` (full existing suite + new training suite — confirms the torch-only addition never leaks into `ance/`)
- **Phase gate:** Full suite green before `/gsd-verify-work`; additionally, the actual overnight training run's artifacts (dataset manifest, fitted K, checkpoint, exported `.safetensors`) are inspected manually as the phase's real deliverable — the automated tests validate *mechanism* correctness (split leakage, format roundtrip, K-fit math), not the trained net's chess strength (that's Phase 5's gauntlet).

### Wave 0 Gaps
- [ ] `tests/training/__init__.py` and `tests/training/conftest.py` — new test package; `conftest.py` should `pytest.importorskip("torch")` for torch-dependent tests only (the `nnue_format` roundtrip test must NOT be skipped when torch is absent — it's numpy-only by design)
- [ ] `tests/training/test_mps_gate.py` — covers TRN-05
- [ ] `tests/training/test_split_no_leakage.py` — covers TRN-02/D-03
- [ ] `tests/training/test_kfit_calibration.py` — covers D-04
- [ ] `tests/training/test_lichess_ingest_sign.py` — covers D-01/D-05 sign correction (Pitfall #3)
- [ ] `tests/training/test_nnue_format_roundtrip.py` — covers TRN-04/D-07 (can be written first — needs no torch, no Stockfish, no real data)
- [ ] `tests/training/test_stockfish_labeler.py` — covers TRN-01; should skip cleanly (not fail) if the `stockfish` binary is absent from PATH, since it's not installed on this machine yet
- [ ] Framework install: `pip install torch numpy safetensors zstandard scipy tqdm` — none of these are in the current `.venv`
- [ ] External tool install: `brew install stockfish` — not currently installed

## Security Domain

`security_enforcement` is not set to `false` in `.planning/config.json` (absent = enabled), so this section is included per protocol. This phase is a local, offline, single-user data/training pipeline with no network-facing service, no authentication surface, and no user-facing input beyond files/config the developer themselves controls — most ASVS categories genuinely do not apply. The categories that do apply concern untrusted *data* (downloaded corpora, external subprocess output), not untrusted *users*.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth surface — local scripts, no service |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A — single local user |
| V5 Input Validation | Yes | Treat downloaded Lichess `.pgn.zst` and any FEN/PGN content as untrusted input (PITFALLS.md already flags this generally): parse defensively with `python-chess`'s own exception handling (`chess.pgn.read_game` returns `None`/skips malformed games rather than raising in most cases, but wrap ingestion in explicit try/except and skip-and-log malformed records rather than crashing a multi-hour run) |
| V6 Cryptography | No | No secrets/crypto in this phase (no lichess-bot token needed here — that's a later/different phase) |
| V12 File & Resources | Yes | Validate any file paths sourced from config (Stockfish binary path, dataset output dirs) are within expected project directories; do not construct paths from unsanitized external input |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/adversarial PGN or FEN in a downloaded corpus crashing the ingestion pipeline mid-run | Denial of Service (against your own multi-hour job, not a remote attacker, but the failure mode is identical) | Wrap per-game parsing in try/except; skip and log rather than abort the whole ingestion pass; this directly protects the D-08 wall-clock budget |
| Loading a checkpoint or shared net via `torch.load` (pickle) from an untrusted source | Tampering / arbitrary code execution via pickle deserialization | Already flagged generally in PITFALLS.md; for this phase specifically — only ever `torch.load` checkpoints this same pipeline just wrote (never a downloaded `.pt`), and the final shipped artifact is safetensors (not pickle) specifically to avoid this class of risk end-to-end (D-07's rationale extends here) |
| Stockfish subprocess driven with an unsanitized/attacker-influenced path or arguments | Tampering (subprocess injection) | The Stockfish binary path and depth/nodes arguments come from project config the developer controls, not external input — no mitigation beyond "don't take these values from an untrusted source" is needed at this phase's scope |

## Sources

### Primary (HIGH confidence)
- `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md`, `.planning/research/STACK.md`, `.planning/PROJECT.md` — this project's own prior HIGH-confidence research, read in full this session
- `ance/eval/base.py`, `ance/board/position.py` — read in full; confirms the `Evaluator` Protocol (STM-relative cp, `MATE=30000`) and the `Position` port surface this phase's exported net must ultimately be compatible with (Phase 5)
- `official-stockfish/nnue-pytorch/docs/nnue.md` (fetched via `raw.githubusercontent.com`) — architecture (768/N/×2/1, ClippedReLU, two-perspective concat order), quantization scale factors (127/64), and the sigmoid-WDL loss formula with lambda blending and the "~400" scaling-constant reference — HIGH, primary/authoritative
- `github.com/pytorch/pytorch` issues #167679 and #177819 (fetched via WebFetch) — confirmed open/unresolved MPS built-but-unavailable regression on macOS 26 (Tahoe) across PyTorch 2.9.1/2.10/2.12-nightly — HIGH confidence the bug exists and remains unresolved; directly relevant because this development machine is running macOS 26.5.2 (confirmed via local `sw_vers`)
- `python-chess` readthedocs `engine.html` (fetched via WebFetch) — `SimpleEngine.analyse()`, `InfoDict["score"]`, `PovScore`/`Cp`/`Mate` semantics, `.relative`/`.white()`/`.black()` — HIGH, official docs
- `huggingface.co/docs/safetensors/api/numpy` (via WebSearch summary) — `safetensors.numpy.save_file`/`load_file` as first-class zero-torch bindings — HIGH, official docs
- Local tool verification this session: `pip index versions {torch,numpy,safetensors,zstandard,tqdm,chess}` — exact current PyPI versions and full release history (used as the package-legitimacy substitute since the automated seam was unavailable); `sw_vers` (macOS 26.5.2 confirmed); `.venv` introspection (none of the new deps currently installed); `which stockfish` (not installed); `df -h` (1.5TB free)

### Secondary (MEDIUM confidence)
- `lichess.org` forum threads + `database.lichess.org` (via WebSearch) — `[%eval]` is White-relative; ~6% of games in the open database carry eval annotations — cross-checked across multiple search results but not fetched from a single canonical spec page
- `github.com/official-stockfish/WDL_model` (referenced via WebSearch summary, not fetched directly) — confirms the logistic-fit methodology for a WDL scaling constant is the same class of technique as this phase's K-fit (D-04)

### Tertiary (LOW confidence — flagged for validation, see Assumptions Log)
- Stockfish labeling throughput/depth-vs-latency estimates for this specific M4 — training-knowledge estimate only, not measured; Open Question #1 recommends a concrete five-minute benchmark task to replace this with a verified figure before the plan commits to a dataset size

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every new package verified against live PyPI registry data this session; roles cross-checked against official docs
- Architecture: HIGH — the `(768→256)×2→1` spec, loss function, and quantization notes come directly from the authoritative `nnue-pytorch/docs/nnue.md` source already cited project-wide
- Pitfalls: HIGH for the MPS-macOS-26 and Lichess-sign-convention findings (both independently verified via WebFetch/WebSearch against primary sources this session, not carried over from training data); MEDIUM for the exact K~400 prior (directional, will be superseded by the empirical fit per D-04 regardless)
- Labeling throughput/depth sizing: LOW — explicitly flagged as unverified (Open Question #1); this is a "measure it, don't guess it" item by design, not a research shortfall

**Research date:** 2026-07-13
**Valid until:** ~30 days for the architecture/stack guidance (stable); the MPS-macOS-26 regression status should be re-checked at execution time if there is any gap between this research and the actual training-harness task, since it is an actively-tracked open issue that could be resolved by a PyTorch patch release in the interim
