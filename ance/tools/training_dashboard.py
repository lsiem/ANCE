"""ANCE live NNUE training dashboard.

Reads ``metrics.json`` (and optional ``training-live.json``) from a training
out-dir and renders loss curves, hyperparameters, and a python-chess SVG board
for the current labeling position or training sample FEN.

Usage:
  .venv/bin/python -m ance.tools.training_dashboard --watch --open
  .venv/bin/python -m ance.tools.training_dashboard --serve --open
"""

from __future__ import annotations

import argparse
import json
import math
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import chess

from ance.tools.gauntlet_board import render_board_svg


def _finite(x: float | None, fallback: float | None = None) -> float | None:
    if x is None:
        return fallback
    if isinstance(x, (int, float)) and math.isfinite(x):
        return float(x)
    return fallback


def _fmt_hms(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = int(max(float(seconds), 0))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    return f"{m}m {sec:02d}s"


def _fmt_loss(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.6f}"


def _resolve_paths(
    *,
    out_dir: Path,
    metrics: Path | None,
    live: Path | None,
    out: Path | None,
) -> tuple[Path, Path, Path]:
    metrics_path = metrics if metrics is not None else out_dir / "metrics.json"
    live_path = live if live is not None else out_dir / "training-live.json"
    out_path = out if out is not None else out_dir / "training-dashboard.html"
    return metrics_path, live_path, out_path


def render_html(
    metrics: dict | None,
    live: dict | None,
    board_svg: str,
    *,
    source_metrics: Path,
    source_live: Path | None,
    board_caption: str,
    fen: str,
) -> str:
    m = metrics or {}
    live = live or {}
    phase = str(live.get("phase") or "")
    is_labeling = phase == "labeling"
    is_generating = phase == "generating"

    status = str(
        m.get("status")
        or (phase if phase in {"labeling", "generating"} else "waiting")
    )
    epoch = int(m.get("epoch") or 0)
    epochs = int(m.get("epochs") or 0)
    epoch_pct = (100.0 * epoch / epochs) if epochs else 0.0
    global_step = int(m.get("global_step") or 0)
    train_losses = list(m.get("train_losses") or [])
    val_losses = list(m.get("val_losses") or [])
    learning_rates = list(m.get("learning_rates") or [])
    best_val = _finite(m.get("best_val_loss"))
    best_epoch = int(m.get("best_epoch") or 0)
    batch_size = m.get("batch_size")
    lr = m.get("lr")
    weight_decay = m.get("weight_decay")
    k_scale = m.get("k")
    device = str(m.get("device") or "—")
    stopped_early = bool(m.get("stopped_early"))
    early_stop_reason = m.get("early_stop_reason")
    updated = m.get("updated_utc") or live.get("updated_utc") or "—"
    checkpoint_dir = m.get("checkpoint_dir") or "—"
    best_checkpoint = m.get("best_checkpoint") or "—"

    label_done = int(live.get("done") or 0)
    label_total = int(live.get("total") or 0)
    label_rate = _finite(live.get("rate_per_s"))
    label_eta = _finite(live.get("eta_s"))
    label_depth = live.get("depth")
    label_pct = (100.0 * label_done / label_total) if label_total else 0.0

    current_lr = learning_rates[-1] if learning_rates else lr
    last_train = _finite(train_losses[-1] if train_losses else None)
    last_val = _finite(val_losses[-1] if val_losses else None)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_metrics": str(source_metrics),
        "source_live": str(source_live) if source_live else None,
        "status": status,
        "epoch": epoch,
        "epochs": epochs,
        "epoch_pct": epoch_pct,
        "global_step": global_step,
        "train_losses": train_losses,
        "val_losses": val_losses,
        "learning_rates": learning_rates,
        "best_val_loss": best_val,
        "best_epoch": best_epoch,
        "batch_size": batch_size,
        "lr": lr,
        "current_lr": current_lr,
        "weight_decay": weight_decay,
        "k": k_scale,
        "device": device,
        "stopped_early": stopped_early,
        "early_stop_reason": early_stop_reason,
        "is_labeling": is_labeling,
        "is_generating": is_generating,
        "label_done": label_done,
        "label_total": label_total,
        "label_pct": label_pct,
        "label_rate": label_rate,
        "label_eta": label_eta,
        "label_depth": label_depth,
        "last_train_loss": last_train,
        "last_val_loss": last_val,
        "fen": fen,
    }
    data_json = json.dumps(payload, allow_nan=False)

    early_pill = ""
    if stopped_early:
        reason = early_stop_reason or "early stop"
        early_pill = f'<span class="pill warn">early stop: {reason}</span>'

    labeling_section = ""
    if is_labeling or is_generating:
        section_title = (
            f"Labeling (Stockfish depth {label_depth})"
            if is_labeling
            else "Generating positions"
        )
        rate_eta = (
            f"rate {label_rate:.2f} pos/s · ETA {_fmt_hms(label_eta)}"
            if is_labeling
            else "random-walk FENs"
        )
        labeling_section = f"""
    <div class="progress">
      <div class="section-title">{section_title}</div>
      <div class="bar"><i style="width:{label_pct:.3f}%"></i></div>
      <div class="progress-meta">
        <span>{label_done:,} / {label_total:,} positions ({label_pct:.1f}%)</span>
        <span>{rate_eta}</span>
      </div>
    </div>
"""

    epoch_section = ""
    if epochs or train_losses:
        epoch_section = f"""
    <div class="progress">
      <div class="section-title">Training epochs</div>
      <div class="bar"><i style="width:{epoch_pct:.3f}%"></i></div>
      <div class="progress-meta">
        <span>epoch {epoch} / {epochs} ({epoch_pct:.1f}%)</span>
        <span>global step {global_step:,}</span>
      </div>
    </div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta http-equiv="refresh" content="4" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ANCE · NNUE training</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap" rel="stylesheet" />
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg0: #12151a;
    --bg1: #1a1f27;
    --bg2: #222933;
    --ink: #eef2f6;
    --muted: #8d9aab;
    --line: #2c3542;
    --nnue: #2fbfa8;
    --hc: #d4a35c;
    --loss: #d65a5a;
    --val: #6ea8e0;
    --win: #5cb87a;
    --warn: #e0b34a;
    --wood: #c4a574;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    color: var(--ink);
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    background:
      radial-gradient(1100px 560px at 12% -12%, #1e3530 0%, transparent 55%),
      radial-gradient(900px 480px at 100% 0%, #2c2418 0%, transparent 48%),
      linear-gradient(180deg, #151922 0%, var(--bg0) 40%, #0e1116 100%);
  }}
  .wrap {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 26px 20px 52px;
  }}
  header.hero {{
    display: grid;
    gap: 6px;
    margin-bottom: 20px;
  }}
  .brand {{
    font-size: clamp(1.75rem, 3.2vw, 2.35rem);
    font-family: "Source Serif 4", Georgia, serif;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: var(--ink);
    line-height: 1.1;
  }}
  .brand span {{ color: var(--nnue); }}
  .subline {{
    font-size: 0.95rem;
    color: var(--muted);
  }}
  .subline strong {{ color: var(--ink); font-weight: 600; }}
  .status-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }}
  .pill {{
    padding: 3px 9px;
    border: 1px solid var(--line);
    background: color-mix(in srgb, var(--bg1) 85%, black);
    font-size: 11px;
    letter-spacing: 0.04em;
  }}
  .pill.live {{
    border-color: color-mix(in srgb, var(--nnue) 55%, var(--line));
    color: var(--nnue);
    animation: pulse 2.4s ease-in-out infinite;
  }}
  .pill.warn {{
    border-color: color-mix(in srgb, var(--warn) 50%, var(--line));
    color: var(--warn);
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.72; }}
  }}

  .stage {{
    display: grid;
    grid-template-columns: minmax(280px, 560px) minmax(260px, 1fr);
    gap: 18px;
    align-items: start;
    margin-bottom: 18px;
  }}
  @media (max-width: 920px) {{
    .stage {{ grid-template-columns: 1fr; }}
  }}
  .board-stage {{
    position: relative;
    background: linear-gradient(160deg, #2a2218 0%, #1a1612 100%);
    border: 1px solid color-mix(in srgb, var(--wood) 35%, var(--line));
    padding: 16px;
    box-shadow: 0 22px 50px rgba(0,0,0,0.4);
  }}
  .board-stage::before {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(135deg, rgba(196,165,116,0.08), transparent 40%);
  }}
  .board-stage svg {{
    display: block;
    width: 100%;
    max-width: 560px;
    height: auto;
    position: relative;
  }}
  .board-caption {{
    margin-top: 10px;
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}
  .instrument {{
    background: var(--bg1);
    border: 1px solid var(--line);
    padding: 14px;
    min-height: 560px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .instrument h2 {{
    margin: 0;
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 1.15rem;
    font-weight: 600;
  }}
  .meta-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }}
  .meta-cell {{
    background: var(--bg2);
    border: 1px solid var(--line);
    padding: 8px 10px;
  }}
  .meta-cell .k {{
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  .meta-cell .v {{
    margin-top: 3px;
    font-size: 14px;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }}
  .fen {{
    font-size: 10px;
    color: var(--muted);
    word-break: break-all;
    line-height: 1.4;
    margin-top: auto;
  }}

  .progress {{
    border: 1px solid var(--line);
    background: var(--bg1);
    padding: 12px 14px;
    margin-bottom: 14px;
  }}
  .section-title {{
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 8px;
  }}
  .bar {{
    height: 12px;
    background: #0b0e12;
    border: 1px solid var(--line);
    overflow: hidden;
  }}
  .bar > i {{
    display: block;
    height: 100%;
    background: linear-gradient(90deg, #1f7a6e, var(--nnue));
    transition: width 0.6s ease;
  }}
  .progress-meta {{
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
    font-size: 11px;
    color: var(--muted);
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 14px;
  }}
  @media (max-width: 860px) {{
    .grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}
  .stat {{
    background: linear-gradient(180deg, color-mix(in srgb, var(--bg1) 90%, white), var(--bg1));
    border: 1px solid var(--line);
    padding: 12px;
  }}
  .stat .label {{
    color: var(--muted);
    font-size: 10px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}
  .stat .value {{
    margin-top: 5px;
    font-size: 1.35rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }}
  .stat .hint {{ margin-top: 3px; color: var(--muted); font-size: 11px; }}

  .charts {{
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 10px;
  }}
  @media (max-width: 900px) {{
    .charts {{ grid-template-columns: 1fr; }}
  }}
  .panel {{
    background: var(--bg1);
    border: 1px solid var(--line);
    padding: 12px;
    min-height: 300px;
  }}
  .panel h3 {{
    margin: 0 0 10px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
  }}
  canvas {{ width: 100% !important; }}
  footer {{
    margin-top: 16px;
    color: var(--muted);
    font-size: 11px;
    line-height: 1.55;
  }}
  footer code {{ color: var(--val); }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <div class="brand">ANCE <span>· training</span></div>
      <div class="subline">
        NNUE offline pipeline · <strong>{device}</strong>
        · K={k_scale if k_scale is not None else '—'}
        · updated {updated}
      </div>
      <div class="status-row">
        <span class="pill {'live' if status in ('running', 'labeling', 'generating') else ''}">{status}</span>
        {'<span class="pill live">labeling live</span>' if is_labeling else ''}
        {'<span class="pill live">generating</span>' if is_generating else ''}
        <span class="pill">batch {batch_size if batch_size is not None else '—'}</span>
        <span class="pill">lr {current_lr if current_lr is not None else lr if lr is not None else '—'}</span>
        {early_pill}
        <span class="pill">refresh 4s</span>
      </div>
    </header>

    <section class="stage" aria-label="Position board">
      <div class="board-stage">
        {board_svg}
        <div class="board-caption">{board_caption}</div>
      </div>
      <aside class="instrument">
        <h2>{'Labeling position' if is_labeling else 'Sample position'}</h2>
        <div class="meta-grid">
          <div class="meta-cell">
            <div class="k">Phase</div>
            <div class="v">{live.get('phase') or status}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Epoch</div>
            <div class="v">{epoch if epoch else '—'} / {epochs if epochs else '—'}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Train loss</div>
            <div class="v">{_fmt_loss(last_train)}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Val loss</div>
            <div class="v">{_fmt_loss(last_val)}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Best val</div>
            <div class="v">{_fmt_loss(best_val)}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Best epoch</div>
            <div class="v">{best_epoch if best_epoch else '—'}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Weight decay</div>
            <div class="v">{weight_decay if weight_decay is not None else '—'}</div>
          </div>
          <div class="meta-cell">
            <div class="k">Global step</div>
            <div class="v">{global_step:,}</div>
          </div>
        </div>
        <div class="fen">FEN {fen}</div>
      </aside>
    </section>

    {labeling_section}
    {epoch_section}

    <div class="grid">
      <div class="stat">
        <div class="label">Best val loss</div>
        <div class="value" style="color: var(--val)">{_fmt_loss(best_val)}</div>
        <div class="hint">epoch {best_epoch if best_epoch else '—'}</div>
      </div>
      <div class="stat">
        <div class="label">Last train loss</div>
        <div class="value" style="color: var(--hc)">{_fmt_loss(last_train)}</div>
        <div class="hint">{len(train_losses)} epochs logged</div>
      </div>
      <div class="stat">
        <div class="label">Last val loss</div>
        <div class="value" style="color: var(--loss)">{_fmt_loss(last_val)}</div>
        <div class="hint">{len(val_losses)} val points</div>
      </div>
      <div class="stat">
        <div class="label">Device</div>
        <div class="value" style="font-size:1.1rem">{device}</div>
        <div class="hint">batch {batch_size if batch_size is not None else '—'}</div>
      </div>
    </div>

    <div class="charts">
      <div class="panel">
        <h3>Train / val loss</h3>
        <canvas id="lossChart" height="160"></canvas>
      </div>
      <div class="panel">
        <h3>Learning rate</h3>
        <canvas id="lrChart" height="160"></canvas>
      </div>
    </div>

    <footer>
      Metrics: {source_metrics}<br/>
      Live: {source_live or '—'} · generated {payload['generated_at']} UTC<br/>
      Checkpoint dir: {checkpoint_dir}<br/>
      Best checkpoint: {best_checkpoint}<br/>
      <code>python -m ance.tools.training_dashboard --serve --open</code>
    </footer>
  </div>

<script>
const DATA = {data_json};

function finiteOrNull(v) {{
  return (typeof v === 'number' && Number.isFinite(v)) ? v : null;
}}

const nEpochs = Math.max(DATA.train_losses.length, DATA.val_losses.length);
const labels = Array.from({{length: nEpochs}}, (_, i) => i + 1);
const trainLoss = DATA.train_losses.map(finiteOrNull);
const valLoss = DATA.val_losses.map(finiteOrNull);
const lrs = DATA.learning_rates.map(finiteOrNull);

new Chart(document.getElementById('lossChart'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [
      {{
        label: 'Train loss',
        data: trainLoss,
        borderColor: '#d4a35c',
        backgroundColor: 'rgba(212,163,92,0.12)',
        fill: false,
        pointRadius: nEpochs < 40 ? 3 : 0,
        borderWidth: 2,
        tension: 0.15,
      }},
      {{
        label: 'Val loss',
        data: valLoss,
        borderColor: '#6ea8e0',
        backgroundColor: 'rgba(110,168,224,0.12)',
        fill: false,
        pointRadius: nEpochs < 40 ? 3 : 0,
        borderWidth: 2,
        tension: 0.15,
      }},
    ]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ labels: {{ color: '#8d9aab' }} }},
      tooltip: {{
        callbacks: {{
          label: (c) => {{
            const v = c.parsed.y;
            return c.dataset.label + ': ' + (v == null ? '—' : v.toFixed(6));
          }}
        }}
      }}
    }},
    scales: {{
      x: {{
        title: {{ display: true, text: 'Epoch', color: '#8d9aab' }},
        ticks: {{ color: '#8d9aab', maxTicksLimit: 12 }},
        grid: {{ color: 'rgba(44,53,66,0.7)' }}
      }},
      y: {{
        title: {{ display: true, text: 'Loss', color: '#8d9aab' }},
        ticks: {{ color: '#8d9aab' }},
        grid: {{ color: 'rgba(44,53,66,0.7)' }},
      }}
    }}
  }}
}});

new Chart(document.getElementById('lrChart'), {{
  type: 'line',
  data: {{
    labels,
    datasets: [{{
      label: 'LR',
      data: lrs.length ? lrs : (DATA.lr != null ? Array(nEpochs).fill(DATA.lr) : []),
      borderColor: '#2fbfa8',
      backgroundColor: 'rgba(47,191,168,0.14)',
      fill: true,
      pointRadius: 0,
      borderWidth: 2,
      tension: 0.2,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{
        ticks: {{ color: '#8d9aab', maxTicksLimit: 12 }},
        grid: {{ color: 'rgba(44,53,66,0.7)' }}
      }},
      y: {{
        ticks: {{ color: '#8d9aab' }},
        grid: {{ color: 'rgba(44,53,66,0.7)' }}
      }}
    }}
  }}
}});
</script>
</body>
</html>
"""


def generate(
    metrics_path: Path,
    out_path: Path,
    *,
    live_path: Path | None = None,
    board_size: int = 560,
) -> dict:
    metrics: dict | None = None
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    live: dict | None = None
    if live_path is not None and live_path.exists():
        live = json.loads(live_path.read_text(encoding="utf-8"))

    phase = str((live or {}).get("phase") or "")
    is_labeling = phase == "labeling"
    is_generating = phase == "generating"
    fen = chess.STARTING_FEN
    board_caption = "Starting position (no live data yet)"
    if is_labeling and live.get("fen"):
        fen = str(live["fen"])
        board_caption = f"Labeling · depth {live.get('depth', '?')} · python-chess board"
    elif is_generating:
        board_caption = "Generating random-walk FENs"
    elif metrics and metrics.get("sample_fen"):
        fen = str(metrics["sample_fen"])
        board_caption = "Training sample FEN · python-chess board"

    board_svg = render_board_svg(fen, size=board_size)
    html = render_html(
        metrics,
        live,
        board_svg,
        source_metrics=metrics_path,
        source_live=live_path if live_path and live_path.exists() else None,
        board_caption=board_caption,
        fen=fen,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    svg_path = out_path.with_name(out_path.stem + "-board.svg")
    svg_path.write_text(board_svg, encoding="utf-8")

    m = metrics or {}
    return {
        "out": str(out_path),
        "svg": str(svg_path),
        "status": m.get("status")
        or (
            phase
            if phase in {"labeling", "generating"}
            else "waiting"
        ),
        "epoch": m.get("epoch"),
        "epochs": m.get("epochs"),
        "best_val_loss": m.get("best_val_loss"),
        "is_labeling": is_labeling,
        "is_generating": is_generating,
        "label_done": (live or {}).get("done"),
        "label_total": (live or {}).get("total"),
        "fen": fen,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    default_out_dir = (
        root / ".planning/phases/04-offline-nnue-training-pipeline/scale-run"
    )

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=default_out_dir,
        help="Training output directory (metrics.json + training-live.json)",
    )
    p.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="Path to metrics.json (default: OUT_DIR/metrics.json)",
    )
    p.add_argument(
        "--live",
        type=Path,
        default=None,
        help="Path to training-live.json (default: OUT_DIR/training-live.json)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="HTML output path (default: OUT_DIR/training-dashboard.html)",
    )
    p.add_argument("--size", type=int, default=560)
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=4.0)
    p.add_argument(
        "--serve",
        action="store_true",
        help="HTTP server: regenerate HTML on every request",
    )
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--open", action="store_true")
    args = p.parse_args(argv)

    metrics_path, live_path, out_path = _resolve_paths(
        out_dir=args.out_dir,
        metrics=args.metrics,
        live=args.live,
        out=args.out,
    )

    if args.serve:
        return _serve(
            metrics=metrics_path,
            live=live_path,
            out=out_path,
            board_size=args.size,
            host=args.host,
            port=args.port,
            open_browser=args.open,
        )

    opened = False
    while True:
        if not metrics_path.exists() and not live_path.exists():
            print(
                f"waiting for metrics or live JSON in {args.out_dir}"
            )
        else:
            info = generate(
                metrics_path,
                out_path,
                live_path=live_path,
                board_size=args.size,
            )
            print(
                f"wrote {info['out']}  status={info['status']} "
                f"epoch={info.get('epoch')}/{info.get('epochs')} "
                f"best_val={info.get('best_val_loss')} "
                f"labeling={info.get('is_labeling')} "
                f"label={info.get('label_done')}/{info.get('label_total')} "
                f"fen={info.get('fen', '')[:40]}"
            )
            if args.open and not opened:
                webbrowser.open(out_path.resolve().as_uri())
                opened = True
        if not args.watch:
            break
        time.sleep(args.interval)
    return 0


def _serve(
    *,
    metrics: Path,
    live: Path,
    out: Path,
    board_size: int,
    host: str,
    port: int,
    open_browser: bool,
) -> int:
    """Serve a freshly regenerated dashboard on every GET /."""

    class Handler(BaseHTTPRequestHandler):
        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except Exception as exc:  # noqa: BLE001
                print(f"request error: {type(exc).__name__}: {exc}")

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/" and path not in ("/index.html", "/dashboard.html"):
                self.send_response(204)
                self.end_headers()
                return
            if not metrics.exists() and not live.exists():
                body = (
                    "<html><body style='font-family:monospace;background:#12151a;"
                    "color:#eef2f6;padding:2rem'>"
                    f"Waiting for metrics or live JSON in {metrics.parent}</body></html>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                info = generate(
                    metrics,
                    out,
                    live_path=live,
                    board_size=board_size,
                )
                html = out.read_bytes()
            except Exception as exc:  # noqa: BLE001
                msg = f"dashboard generate failed: {type(exc).__name__}: {exc}"
                print(msg)
                body = (
                    "<html><body style='font-family:monospace;background:#12151a;"
                    f"color:#eef2f6;padding:2rem'>{msg}</body></html>"
                ).encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            print(
                f"GET / status={info.get('status')} "
                f"epoch={info.get('epoch')}/{info.get('epochs')} "
                f"best_val={info.get('best_val_loss')} "
                f"label={info.get('label_done')}/{info.get('label_total')}"
            )

        def log_message(self, fmt: str, *a: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"ANCE training dashboard at {url}")
    print(f"  metrics: {metrics}")
    print(f"  live:    {live}")
    print("  each browser refresh regenerates from metrics + live JSON")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
