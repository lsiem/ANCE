<!-- GSD:project-start source:PROJECT.md -->
## Project

**ANCE — A Neural-network Chess Engine**

A UCI-compatible chess engine built in Python, whose playing strength comes
from a supervised-trained NNUE-style neural evaluation driving a classical
alpha-beta search. Built for a single Apple Silicon M4 Mac (24 GB unified
memory) as a learning-and-strength project: reach a genuinely strong,
GUI-playable engine without the ruinous compute of AlphaZero-style self-play.

**Core Value:** The engine plays legal, tactically sound chess through a clean UCI interface,
and gets measurably stronger when a trained NNUE evaluation replaces the
handcrafted one. If everything else fails, a swappable-eval alpha-beta engine
that loads and runs a trained network must work.

### Constraints

- **Tech stack**: Python 3.12+, `python-chess`, PyTorch (MPS) — matches M4 and
  the Python-first decision
- **Hardware**: Single M4 Mac, 24 GB shared memory — cap batch/minibatch sizes;
  no distributed/multi-GPU training
- **Performance**: Pure-Python search caps strength this milestone; hot-path port
  is explicitly out of scope here
- **Compute budget**: No from-scratch self-play; strength via supervised
  pretraining only. Heavy/large training runs deferred to future cloud/NVIDIA work
- **Architecture boundary**: Evaluation must be a swappable module so the NNUE
  can replace the handcrafted eval without touching the search, and so search+eval
  can later be ported to a compiled language
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Engine + trainer language | Committed project decision; native **arm64** build required (NOT Rosetta) so PyTorch MPS and numeric libs hit Apple Silicon. 3.12 is well-supported by every dependency below; 3.10+ is the floor set by lichess-bot. |
| python-chess (`chess`) | 1.11.2 | Board state, legal movegen, FEN/PGN, SAN↔UCI, repetition/50-move | The de-facto Python chess library. Pure Python, zero compiled deps, exhaustively correct movegen. We use it for the *board*, not the UCI I/O — we write our own stdin/stdout UCI loop; `chess.engine` is only for *driving* external engines (Stockfish labeling, gauntlets). NOTE: now published on PyPI as **`chess`** (`pip install chess`); `python-chess` is an alias. |
| PyTorch | 2.x stable (verify latest, ~2.11) with **MPS** backend | Train the NNUE net on the M4 GPU | Standard DL framework; MPS ships in the normal wheels (no special build). Recommended for residual/NNUE-style nets on M4 over MLX due to maturity, ecosystem, and portability of the trained weights. Requires macOS 12.3+. See MPS caveats below. |
| NumPy | 2.x | Feature encoding, quantization math, data marshaling | Sparse 768-input feature vectors, int8/int16 quantization arithmetic, and fast dataset transforms. Pairs with PyTorch tensors. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `zstandard` (or `python-zstd`) | latest | Decompress Lichess `.pgn.zst` dumps | When ingesting the Lichess Open Database (files are zstd-compressed, tens of GB each). |
| `numpy` structured arrays / `.npy` | — | On-disk training-sample format | Serialize (encoded position, label) pairs for fast epoch reloading instead of re-parsing PGN each epoch. |
| `tqdm` | latest | Progress bars for labeling + training | Long Stockfish-labeling passes and training loops. |
| `PyYAML` | latest | lichess-bot `config.yml` | Only for the lichess-bot deployment step (it already vendors this). |
| `pytest` | 8.x | Test the UCI loop, search, eval boundary | Table-driven tests for movegen correctness, UCI command handling, and eval-swap interface stability (project mandates the eval stays swappable). |
| `python-chess` `.polyglot` / `.syzygy` | (bundled) | Optional opening book / endgame tablebase probing | Later polish; not needed for M1–M3. |
### Development / External Tools
| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| Stockfish | 17.1 (2025-03-30); 18 on download page | (1) Label generator for supervised NNUE data; (2) gauntlet/sparring opponent | `brew install stockfish` → `/opt/homebrew/opt/stockfish`, or the `stockfish-macos-m1-apple-silicon` binary. Drive it from Python via `chess.engine.SimpleEngine.popen_uci(...)` to score positions to a fixed depth/nodes. |
| Cute Chess / `cutechess-cli` | 1.5.1 (2026-06-14) | Engine-vs-engine gauntlets, SPRT, Elo measurement | The standard for "measurable Elo gain (NNUE vs handcrafted)". Prebuilt macOS assets on the release page; building from source needs Qt 6.8+, C++17, cmake. Run `cutechess-cli` headless in CI/scripts. |
| lichess-bot | latest (`lichess-bot-devs/lichess-bot`) | Make ANCE playable online | Python **3.10+**. Point `config.yml` at the ANCE launch command; needs a Lichess BOT account + API token. Used for the "playable via lichess-bot" requirement. |
| Lc0 (Leela Chess Zero) | latest (v0.31+) | Optional superhuman sparring/analysis opponent | Metal backend is the **default** on macOS builds (faster than OpenCL). `brew install lc0` or binaries from lczero.org; requires a network weights file. Used ONLY as an opponent — it is an MCTS/policy-value engine, explicitly NOT ANCE's paradigm. |
| Arena / Cute Chess GUI | — | Manual play-testing in a GUI | Satisfies the "validated in a GUI" requirement; Cute Chess GUI ships alongside the CLI. |
## Installation
# --- Python engine + trainer (native arm64 venv) ---
# Verify: python -c "import platform; print(platform.machine())"  -> arm64
# Core
# Supporting (data + training ergonomics)
# Dev
# --- External engines / tooling (Homebrew) ---
# Cute Chess: download the 1.5.1 macOS build from
#   https://github.com/cutechess/cutechess/releases  (cutechess-cli for gauntlets)
# --- lichess-bot (separate checkout, its own requirements) ---
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| PyTorch MPS | **MLX** (Apple's array framework) | If you hit MPS op gaps/bugs that block training, MLX is a native-Metal option worth a spike. But it has a smaller ecosystem, non-portable weights, and less NNUE precedent — current evidence favors PyTorch MPS for this net class on M4. Keep MLX as an experiment, not the baseline. |
| Hand-written NNUE trainer in PyTorch (nnue-pytorch as *reference*) | **jw1912/bullet** | Bullet is the SOTA trainer used by most top engines and — new finding — now has a `metal` feature flag (alongside `cuda`/`rocm`), so it *can* run on Apple Silicon. Adopt it only in a later scale-up milestone: it is Rust (not Python-first), its tuning/docs are CUDA-centric, the Metal path is newer/less battle-tested, and M4 neural throughput trails NVIDIA. For an understandable, swappable-eval M1 milestone, a small PyTorch training loop following `nnue-pytorch/docs/nnue.md` is the right call. |
| Stockfish for labels | **Lc0 for labels**, or **reuse Lichess `[%eval]` tags** | Reuse existing Lichess `[%eval]` annotations (~6% of games, SF-NNUE @ 40 Mnodes) to skip a labeling pass. Use fresh Stockfish labels when you want controlled depth/coverage of your own position set. Lc0 labels are WDL/policy-flavored and off-paradigm — avoid for NNUE cp targets. |
| Cute Chess `cutechess-cli` | **fastchess** | fastchess is a faster modern gauntlet runner; fine substitute if cutechess build/Qt friction appears. Cute Chess also gives you the GUI, satisfying two requirements with one tool. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `bullet` as the M1 trainer | Rust, CUDA-centric tuning/docs, Metal path immature; overkill for a plain `(768→N)×2→1` net; conflicts with the Python-first, understandable-code decision | PyTorch MPS training loop guided by `nnue-pytorch/docs/nnue.md` |
| `chess.engine` for the UCI loop | It is a *client* that drives external engines; ANCE must *be* the engine and speak UCI on its own stdin/stdout | Hand-written UCI I/O loop; use `python-chess` only for board/movegen |
| Rosetta / x86 Python | MPS won't engage; silent perf cliff and dtype surprises | Native **arm64** Python 3.12 |
| `float64` anywhere in the training path | MPS does not support float64 — raises `TypeError: Cannot convert a MPS Tensor to float64` | float32 throughout; int8/int16 only at quantization/export |
| AMP/FP16 mixed precision "for speed" | M4 has no tensor-core equivalent — little/no speedup, added bug surface | Plain float32 on MPS; the net is tiny, memory isn't the constraint |
| AlphaZero/MCTS/self-play frameworks | Out of scope and infeasible on one M4; NNUE + alpha-beta is the committed vehicle | Supervised NNUE, classical alpha-beta |
| Bleeding-edge PyTorch on a brand-new macOS | Reported MPS *built-but-unavailable* regressions on macOS 26 (Tahoe) with PyTorch 2.9–2.10 (issues #167679, #177819) | Pin a PyTorch version verified `mps.is_available()==True` on the actual macOS build before committing |
## MPS / M4-Specific Constraints (READ BEFORE TRAINING)
- **No float64.** Keep the entire training graph in float32. Watch out for libraries that silently upcast (e.g. some loss/metric helpers).
- **Set `PYTORCH_ENABLE_MPS_FALLBACK=1`** so unimplemented ops fall back to CPU rather than crashing. Fallback is slower and has occasional edge-case bugs (e.g. some `Conv1d` shapes) — but NNUE is Linear + ClippedReLU only, so op coverage is not a real risk here.
- **Historical silent kernel bugs** (`addcmul_`/`addcdiv_` on non-contiguous outputs → corrupted Adam state) were fixed in recent PyTorch + macOS 15+. Use a current PyTorch and a current macOS; if training diverges inexplicably, suspect MPS and cross-check one epoch on `device="cpu"`.
- **Weak FP16/AMP benefit** — don't bother; train in float32.
- **Verify availability on the target OS.** `torch.backends.mps.is_available()` has regressed on new macOS majors; make this a project-init gate, not an assumption.
- **24 GB unified memory** is ample for a `(768→N)×2→1` net (N in the low hundreds). The bottleneck is data pipeline throughput (PGN parse / Stockfish labeling), not GPU memory — pre-encode samples to `.npy` and cache.
## NNUE Reference Architecture (from `nnue-pytorch/docs/nnue.md`)
- Start with **plain `(768→N)×2→1`**: two perspectives (side-to-move / not), one shared feature transformer, one hidden layer, single scalar output. No king buckets.
- **Inputs:** sparse 768 = 64 squares × 6 piece types × 2 colors, per perspective; incremental **accumulator** updated on make/unmake.
- **Layers:** Linear + **ClippedReLU** (`clamp(0,1)`) — deliberately low-precision-friendly.
- **Quantization for the engine:** feature transformer weights + accumulator → **int16**; hidden linear weights → **int8** (narrow range, ~activation 0..1). Clamp params to the quantized range **after each optimizer step** during training to prevent train/inference divergence.
- Train in float32 on MPS; export quantized int8/int16 weights for the CPU alpha-beta leaf eval. This is exactly what keeps the eval swappable and portable to a future compiled port.
## Stack Patterns by Variant
- Train on `device="cpu"` for the tiny `(768→N)×2→1` net (slow but correct), and file the macOS/PyTorch combo as a research flag.
- Because the net is small, CPU training is a viable fallback, not a blocker.
- Skip a custom Stockfish labeling pass; parse `[%eval]` directly from PGN → faster path to first net.
- Move to `bullet` (CUDA on cloud NVIDIA, or its `metal` flag on the M4 as an experiment) and/or king-bucketed bigger nets — deferred per PROJECT.md.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| PyTorch (MPS) | macOS 12.3+ / arm64 Python | bf16 needs macOS 14+; verify `mps.is_available()` on macOS 26 (Tahoe) — regressions reported on 2.9–2.10. |
| lichess-bot | Python 3.10+ | Separate venv/checkout; keep isolated from the engine venv if versions ever conflict. |
| Cute Chess (build) | Qt 6.8+, C++17, cmake | Prefer the prebuilt 1.5.1 macOS binary to avoid a Qt toolchain. |
| python-chess (`chess`) 1.11.2 | Python 3.8+ | Import name is `chess`; `pip install python-chess` also works as an alias. |
| Stockfish (UCI) | any GUI / `chess.engine` | Driven over UCI; version-agnostic for labeling. |
## Sources
- `/niklasf/python-chess` (Context7) — python-chess v1.11.2, capabilities — MEDIUM
- pypi.org/project/chess, readthedocs python-chess changelog — package rename to `chess`, 1.11.2 — MEDIUM (cross-checked)
- developer.apple.com/metal/pytorch, docs.pytorch.org/docs/stable/notes/mps.html — MPS requirements, float64/fallback caveats — MEDIUM
- github.com/pytorch/pytorch issues #167679, #177819 — MPS-unavailable-on-macOS-26 regression — LOW (issue reports; verify locally)
- github.com/official-stockfish/nnue-pytorch `docs/nnue.md` — NNUE architecture + quantization — HIGH (primary/authoritative doc)
- github.com/jw1912/bullet `docs/2-getting-started.md` — CUDA/ROCm/**Metal** backend feature flags — MEDIUM (official docs; Metal path newness not stress-tested)
- github.com/cutechess/cutechess/releases — Cute Chess 1.5.1 (2026-06-14), Qt 6.8+ — MEDIUM
- github.com/lichess-bot-devs/lichess-bot wiki — Python 3.10+ requirement — MEDIUM
- stockfishchess.org/download, formulae.brew.sh/formula/stockfish — Stockfish 17.1/18, `brew install stockfish` — MEDIUM
- lczero.org/play/download, LeelaChessZero/lc0 — Metal default backend on macOS — MEDIUM
- database.lichess.org, github.com/lichess-org/database — zstd PGN dumps, ~6% with SF-NNUE `[%eval]` — MEDIUM
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
