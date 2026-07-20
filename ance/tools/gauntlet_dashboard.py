"""ANCE live gauntlet / match control dashboard.

Combines:
  - python-chess SVG board (``chess.svg.board``) for the live game
  - Elo / Wilson CI / score-rate charts from the checkpoint
  - Clocks, material, move list, D-12 gate status

The same board renderer and visual shell are intended for future offline
training dashboards (loss curves, dataset stats, sample positions).

Usage:
  .venv/bin/python -m ance.tools.gauntlet_dashboard --watch --open
"""

from __future__ import annotations

import argparse
import html
import json
import math
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import chess

from ance.tools.gauntlet import score_rate_to_elo, wilson_ci
from ance.tools.gauntlet_board import render_board_svg
from ance.tools.stockfish_eval import StockfishAnalyzer, find_stockfish


def _finite(x: float | None, fallback: float | None = None) -> float | None:
    if x is None:
        return fallback
    if isinstance(x, (int, float)) and math.isfinite(x):
        return float(x)
    return fallback


def _outcome_score(outcome: str) -> float:
    if outcome == "win":
        return 1.0
    if outcome == "draw":
        return 0.5
    return 0.0


def build_series(games: list[dict]) -> dict:
    scores: list[float] = []
    running_score = 0.0
    elo_point: list[float | None] = []
    elo_low: list[float | None] = []
    elo_high: list[float | None] = []
    score_rates: list[float] = []
    outcomes: list[str] = []
    elapsed_s: list[float] = []
    moves: list[int] = []
    a_white: list[bool] = []

    for i, g in enumerate(games, start=1):
        outcome = str(g.get("outcome", "loss"))
        outcomes.append(outcome)
        running_score += _outcome_score(outcome)
        scores.append(running_score)
        p = running_score / i
        score_rates.append(p)
        w_low, w_high = wilson_ci(running_score, i)
        elo_point.append(_finite(score_rate_to_elo(p)))
        elo_low.append(_finite(score_rate_to_elo(w_low)))
        elo_high.append(_finite(score_rate_to_elo(w_high)))
        elapsed_s.append(float(g.get("elapsed_s") or 0.0))
        moves.append(int(g.get("moves") or 0))
        a_white.append(bool(g.get("a_is_white")))

    return {
        "n": len(games),
        "scores": scores,
        "score_rates": score_rates,
        "elo_point": elo_point,
        "elo_low": elo_low,
        "elo_high": elo_high,
        "outcomes": outcomes,
        "elapsed_s": elapsed_s,
        "moves": moves,
        "a_white": a_white,
    }


def _format_moves(sans: list[str]) -> str:
    if not sans:
        return "<div class='muted'>Waiting for first move…</div>"
    rows: list[str] = []
    for i in range(0, len(sans), 2):
        num = i // 2 + 1
        white = html.escape(sans[i])
        black = html.escape(sans[i + 1]) if i + 1 < len(sans) else ""
        rows.append(
            f"<div class='ply'><span class='n'>{num}.</span> "
            f"<span class='w'>{white}</span> "
            f"<span class='b'>{black}</span></div>"
        )
    return "\n".join(rows)


def _fmt_clock(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = max(float(seconds), 0.0)
    m, sec = divmod(s, 60.0)
    return f"{int(m)}:{sec:04.1f}"


def _fmt_hms(seconds: float) -> str:
    s = int(max(seconds, 0))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    return f"{m}m {sec:02d}s"


def _fmt_elo(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}"


def _fmt_material(cp: int | None) -> str:
    if cp is None:
        return "—"
    pawns = cp / 100.0
    return f"{pawns:+.1f}" if cp != 0 else "0.0"


def render_html(
    checkpoint: dict,
    series: dict,
    live: dict | None,
    board_svg: str,
    source_ckpt: Path,
    source_live: Path | None,
    sf_eval: dict | None = None,
) -> tuple[str, dict]:
    agg = checkpoint.get("aggregate") or {}
    params = checkpoint.get("parameters") or {}
    sf = sf_eval or {}
    sf_pct = float(sf.get("white_win_pct") if sf.get("white_win_pct") is not None else 50.0)
    sf_label = str(sf.get("label") or "—")
    sf_depth = sf.get("depth")
    sf_pv = " ".join(sf.get("pv_san") or [])
    sf_best = sf.get("bestmove_uci") or "—"
    sf_available = bool(sf)
    n_target = int(params.get("n_games") or 0)
    n_done = int(series["n"])
    status = checkpoint.get("status", "unknown")
    mode = params.get("mode", "?")
    depth = params.get("search_depth")
    engine_a = (params.get("engine_a") or {}).get("name", "A")
    engine_b = (params.get("engine_b") or {}).get("name", "B")
    env_a = (params.get("engine_a") or {}).get("env") or {}
    env_b = (params.get("engine_b") or {}).get("env") or {}

    wins = int(agg.get("wins") or 0)
    losses = int(agg.get("losses") or 0)
    draws = int(agg.get("draws") or 0)
    elapsed = float(agg.get("elapsed_s") or sum(series["elapsed_s"]))
    pace = (elapsed / n_done) if n_done else 0.0
    eta_s = pace * max(n_target - n_done, 0)
    pct = (100.0 * n_done / n_target) if n_target else 0.0

    elo = _finite(agg.get("elo"))
    elo_lo = _finite(agg.get("elo_ci_low"))
    elo_hi = _finite(agg.get("elo_ci_high"))
    score_rate = float(agg.get("score_rate") or 0.0)
    d12_pass = bool(
        elo is not None
        and elo_lo is not None
        and elo > 0
        and elo_lo > 0
        and n_done >= n_target
    )

    live = live or {}
    fen = live.get("fen") or chess.STARTING_FEN
    white = live.get("white") or engine_a
    black = live.get("black") or engine_b
    turn = live.get("turn") or "white"
    thinker = white if turn == "white" else black
    game_index = live.get("game_index")
    game_label = (
        f"{int(game_index) + 1}" if isinstance(game_index, int) else (str(game_index) if game_index is not None else "—")
    )
    n_games_live = live.get("n_games") or n_target
    halfmoves = live.get("halfmoves") or 0
    last_san = live.get("last_san")
    if not last_san:
        sans = list(live.get("san_moves") or [])
        last_san = sans[-1] if sans else "—"
    last_think = live.get("last_think_s")
    last_think_s = f"{float(last_think):.1f}s" if last_think is not None else "—"
    in_check = bool(live.get("in_check"))
    material = live.get("material") or {}
    bal = material.get("balance_cp")
    moves_block = _format_moves(list(live.get("san_moves") or []))
    live_updated = live.get("updated_utc") or "—"

    w_clock_s = float(live.get("white_clock_s") or live.get("tc_base_s") or 0.0)
    b_clock_s = float(live.get("black_clock_s") or live.get("tc_base_s") or 0.0)
    w_clock = _fmt_clock(w_clock_s)
    b_clock = _fmt_clock(b_clock_s)
    thinking = bool(live.get("thinking"))
    think_elapsed = live.get("think_elapsed_s")
    check_badge = '<span class="badge check">CHECK</span>' if in_check else ""
    live_note = live.get("note") or ""

    change_key = "|".join(
        [
            str(status),
            str(n_done),
            str(wins),
            str(draws),
            str(losses),
            str(elo),
            str(elo_lo),
            str(game_index),
            str(halfmoves),
            str(fen),
            str(last_san),
            str(thinking),
            str(sf_label),
            str(live_updated),
            str(series.get("n")),
        ]
    )
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": str(source_ckpt),
        "live_source": str(source_live) if source_live else None,
        "status": status,
        "n_done": n_done,
        "n_target": n_target,
        "pct": pct,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score_rate": score_rate,
        "elo": elo,
        "elo_ci_low": elo_lo,
        "elo_ci_high": elo_hi,
        "elapsed_s": elapsed,
        "eta_s": eta_s,
        "pace_s": pace,
        "mode": mode,
        "depth": depth,
        "engine_a": engine_a,
        "engine_b": engine_b,
        "env_a": env_a,
        "env_b": env_b,
        "series": series,
        "d12_pass": d12_pass,
        "change_key": change_key,
        "board_svg": board_svg,
        "moves_html": moves_block,
        "fen": fen,
        "white": white,
        "black": black,
        "turn": turn,
        "thinker": thinker,
        "game_label": game_label,
        "n_games_live": n_games_live,
        "halfmoves": halfmoves,
        "last_san": last_san,
        "last_think_s": last_think_s,
        "in_check": in_check,
        "material_balance": _fmt_material(bal) if isinstance(bal, int) else "—",
        "material_white": (material.get("white_cp") or 0) / 100.0,
        "material_black": (material.get("black_cp") or 0) / 100.0,
        "piece_count": live.get("piece_count") or "—",
        "opening_index": live.get("opening_index", "—"),
        "live_updated": live_updated,
        "live_note": live_note,
        "live_missing": not bool(live.get("fen")),
        "white_clock_s": w_clock_s,
        "black_clock_s": b_clock_s,
        "thinking": thinking,
        "think_elapsed_s": think_elapsed,
        "white_env": live.get("white_env") or env_a,
        "black_env": live.get("black_env") or env_b,
        "sf_available": sf_available,
        "sf_label": sf_label,
        "sf_pct": sf_pct,
        "sf_depth": sf_depth,
        "sf_pv": sf_pv,
        "sf_best": sf_best,
        "env_a_eval": env_a.get("ANCE_EVAL", "?"),
        "env_b_eval": env_b.get("ANCE_EVAL", "?"),
        "elapsed_hms": _fmt_hms(elapsed),
        "eta_hms": _fmt_hms(eta_s),
        "elo_fmt": _fmt_elo(elo),
        "elo_lo_fmt": _fmt_elo(elo_lo),
        "elo_hi_fmt": _fmt_elo(elo_hi),
        "score_rate_pct": f"{score_rate:.1%}",
    }
    data_json = json.dumps(payload, allow_nan=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ANCE · {engine_a} vs {engine_b}</title>
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
    --win: #5cb87a;
    --draw: #8d9aab;
    --accent: #6ea8e0;
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
  .brand span {{
    color: var(--nnue);
  }}
  .match-line {{
    font-size: 0.95rem;
    color: var(--muted);
  }}
  .match-line strong {{ color: var(--ink); font-weight: 600; }}
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

  /* —— Live board stage (primary composition) —— */
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
  .board-with-eval {{
    display: grid;
    grid-template-columns: 28px minmax(0, 1fr);
    gap: 10px;
    align-items: stretch;
  }}
  .eval-bar {{
    position: relative;
    border-radius: 4px;
    overflow: hidden;
    background: #111;
    border: 1px solid var(--line);
    min-height: 280px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }}
  .eval-bar .black-fill {{
    position: absolute;
    inset: 0;
    background: #1a1a1a;
  }}
  .eval-bar .white-fill {{
    position: relative;
    z-index: 1;
    width: 100%;
    height: 50%;
    background: #f0f0f0;
    transition: height 0.35s ease;
  }}
  .eval-bar .eval-label {{
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    z-index: 2;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: -0.02em;
    writing-mode: horizontal-tb;
    padding: 2px 0;
    color: #111;
    bottom: 6px;
  }}
  .eval-meta {{
    margin-top: 8px;
    font-size: 11px;
    color: var(--muted);
    line-height: 1.45;
  }}
  .eval-meta strong {{ color: var(--ink); }}
  .board-stage {{
    position: relative;
    background:
      linear-gradient(160deg, #2a2218 0%, #1a1612 100%);
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
    padding: 14px 14px 12px;
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
    letter-spacing: -0.02em;
  }}
  .seats {{ display: grid; gap: 8px; }}
  .seat {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 4px 12px;
    padding: 10px 12px;
    background: var(--bg2);
    border: 1px solid var(--line);
    border-left: 3px solid transparent;
    transition: border-color 0.25s ease, background 0.25s ease;
  }}
  .seat.active {{
    border-left-color: var(--nnue);
    background: color-mix(in srgb, var(--bg2) 70%, #1e3530);
  }}
  .seat .name {{ font-weight: 600; font-size: 14px; }}
  .seat .tag {{ font-size: 11px; color: var(--muted); }}
  .seat .clock {{
    font-size: 1.25rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    align-self: center;
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
  }}
  .badge.check {{
    color: var(--loss);
    font-weight: 700;
    margin-left: 6px;
  }}
  .thinking {{
    font-size: 12px;
    color: var(--muted);
    line-height: 1.55;
  }}
  .thinking strong {{ color: var(--nnue); }}
  .moves {{
    flex: 1;
    overflow: auto;
    max-height: 220px;
    border-top: 1px solid var(--line);
    padding-top: 10px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 12px;
    font-size: 12px;
  }}
  .ply .n {{ color: var(--muted); }}
  .ply .w {{ color: var(--ink); }}
  .ply .b {{ color: var(--hc); }}
  .muted {{ color: var(--muted); }}
  .fen {{
    font-size: 10px;
    color: var(--muted);
    word-break: break-all;
    line-height: 1.4;
  }}

  /* —— Aggregate instruments —— */
  .progress {{
    border: 1px solid var(--line);
    background: var(--bg1);
    padding: 12px 14px;
    margin-bottom: 14px;
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
    width: 0%;
    background: linear-gradient(90deg, #1f7a6e, var(--nnue));
    transition: width 0.6s ease;
  }}
  .progress .meta {{
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
    font-size: 1.45rem;
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
  .outcome-strip {{
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    margin-top: 12px;
  }}
  .outcome-strip span {{
    width: 9px;
    height: 9px;
    background: var(--draw);
  }}
  .outcome-strip span.win {{ background: var(--win); }}
  .outcome-strip span.loss {{ background: var(--loss); }}
  .outcome-strip span.draw {{ background: var(--draw); }}
  footer {{
    margin-top: 16px;
    color: var(--muted);
    font-size: 11px;
    line-height: 1.55;
  }}
  footer code {{ color: var(--accent); }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <div class="brand">ANCE <span>· live match</span></div>
      <div class="match-line" id="match-line"></div>
      <div class="status-row" id="status-row"></div>
    </header>

    <section class="stage" aria-label="Live game">
      <div class="board-stage">
        <div class="board-with-eval">
          <div class="eval-bar" title="Stockfish eval (white POV)">
            <div class="black-fill"></div>
            <div class="white-fill" id="eval-white-fill"></div>
            <div class="eval-label" id="eval-label">—</div>
          </div>
          <div id="board-svg">{board_svg}</div>
        </div>
        <div class="board-caption" id="board-caption"></div>
        <div class="eval-meta" id="eval-meta"></div>
      </div>
      <aside class="instrument">
        <h2 id="game-title">Game —</h2>
        <div class="seats">
          <div class="seat" id="seat-black">
            <div>
              <div class="name" id="name-black">{black}</div>
              <div class="tag" id="tag-black"></div>
            </div>
            <div class="clock" id="clock-black">{b_clock}</div>
          </div>
          <div class="seat" id="seat-white">
            <div>
              <div class="name" id="name-white">{white}</div>
              <div class="tag" id="tag-white"></div>
            </div>
            <div class="clock" id="clock-white">{w_clock}</div>
          </div>
        </div>
        <div class="thinking" id="thinking"></div>
        <div class="meta-grid">
          <div class="meta-cell">
            <div class="k">Material W / B</div>
            <div class="v" id="meta-material">—</div>
          </div>
          <div class="meta-cell">
            <div class="k">Pieces</div>
            <div class="v" id="meta-pieces">—</div>
          </div>
          <div class="meta-cell">
            <div class="k">Opening #</div>
            <div class="v" id="meta-opening">—</div>
          </div>
          <div class="meta-cell">
            <div class="k">Updated</div>
            <div class="v" id="meta-updated" style="font-size:11px">—</div>
          </div>
        </div>
        <div class="moves" id="moves"></div>
        <div class="fen" id="fen"></div>
      </aside>
    </section>

    <div class="progress">
      <div class="bar"><i id="progress-bar"></i></div>
      <div class="meta">
        <span id="progress-left"></span>
        <span id="progress-right"></span>
      </div>
    </div>

    <div class="grid">
      <div class="stat">
        <div class="label">Elo (point)</div>
        <div class="value" id="stat-elo" style="color: var(--accent)">—</div>
        <div class="hint" id="stat-elo-hint">95% CI</div>
      </div>
      <div class="stat">
        <div class="label">Score rate</div>
        <div class="value" id="stat-rate">—</div>
        <div class="hint" id="stat-wdl">W–D–L</div>
      </div>
      <div class="stat">
        <div class="label">D-12 gate</div>
        <div class="value" id="stat-d12" style="color: var(--warn)">OPEN</div>
        <div class="hint">Elo&gt;0 and CI<sub>low</sub>&gt;0 at 1000</div>
      </div>
      <div class="stat">
        <div class="label">Sample</div>
        <div class="value" id="stat-sample">0</div>
        <div class="hint" id="stat-sample-hint">target</div>
      </div>
    </div>

    <div class="charts">
      <div class="panel">
        <h3>Running Elo + Wilson CI</h3>
        <canvas id="eloChart" height="140"></canvas>
      </div>
      <div class="panel">
        <h3>Results mix</h3>
        <canvas id="mixChart" height="140"></canvas>
        <div class="outcome-strip" id="strip"></div>
      </div>
    </div>

    <div class="panel" style="margin-top:10px; min-height:auto">
      <h3>Score rate over games</h3>
      <canvas id="rateChart" height="90"></canvas>
    </div>

    <footer id="footer"></footer>
  </div>

<script>
let DATA = {data_json};
let lastChangeKey = null;
let lastChartsKey = null;
let eloChart = null;
let mixChart = null;
let rateChart = null;
let clockState = {{
  turn: 'white', thinking: false, think_elapsed_s: 0,
  white_clock_s: 0, black_clock_s: 0,
}};
let clockPageLoaded = Date.now();

function escapeHtml(v) {{
  return String(v ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

function finiteOrNull(v) {{
  return (typeof v === 'number' && Number.isFinite(v)) ? v : null;
}}

function fmtClock(sec) {{
  sec = Math.max(0, Number(sec) || 0);
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return m + ':' + s.toFixed(1).padStart(4, '0');
}}

function seriesFrom(d) {{
  const n = Number(d.n_done || 0);
  const labels = Array.from({{length: n}}, (_, i) => i + 1);
  const series = d.series || {{}};
  return {{
    n,
    labels,
    elo: (series.elo_point || []).map(finiteOrNull),
    eloLo: (series.elo_low || []).map(finiteOrNull),
    eloHi: (series.elo_high || []).map(finiteOrNull),
    rates: series.score_rates || [],
    outcomes: series.outcomes || [],
  }};
}}

function chartsKey(d) {{
  return [
    d.n_done, d.wins, d.draws, d.losses,
    (d.series && d.series.n) || 0,
  ].join('|');
}}

function ensureCharts(d) {{
  if (typeof Chart === 'undefined') {{
    console.warn('Chart.js failed to load; charts skipped');
    return;
  }}
  const s = seriesFrom(d);
  if (!eloChart) {{
    eloChart = new Chart(document.getElementById('eloChart'), {{
      type: 'line',
      data: {{
        labels: s.labels,
        datasets: [
          {{
            label: 'Elo CI high',
            data: s.eloHi,
            borderColor: 'rgba(110,168,224,0.35)',
            backgroundColor: 'rgba(110,168,224,0.12)',
            fill: '+1',
            pointRadius: 0,
            borderWidth: 1,
            tension: 0.2,
          }},
          {{
            label: 'Elo CI low',
            data: s.eloLo,
            borderColor: 'rgba(110,168,224,0.35)',
            backgroundColor: 'transparent',
            fill: false,
            pointRadius: 0,
            borderWidth: 1,
            tension: 0.2,
          }},
          {{
            label: 'Elo point',
            data: s.elo,
            borderColor: '#2fbfa8',
            backgroundColor: '#2fbfa8',
            pointRadius: s.n < 40 ? 3 : 0,
            borderWidth: 2,
            tension: 0.15,
          }},
        ]
      }},
      options: {{
        responsive: true,
        animation: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ labels: {{ color: '#8d9aab' }} }},
          tooltip: {{
            callbacks: {{
              label: (c) => {{
                const v = c.parsed.y;
                return c.dataset.label + ': ' + (v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(1));
              }}
            }}
          }}
        }},
        scales: {{
          x: {{
            title: {{ display: true, text: 'Games', color: '#8d9aab' }},
            ticks: {{ color: '#8d9aab', maxTicksLimit: 10 }},
            grid: {{ color: 'rgba(44,53,66,0.7)' }}
          }},
          y: {{
            title: {{ display: true, text: 'Elo', color: '#8d9aab' }},
            ticks: {{ color: '#8d9aab' }},
            grid: {{ color: 'rgba(44,53,66,0.7)' }},
            suggestedMin: -400,
            suggestedMax: 400,
          }}
        }}
      }}
    }});
  }}
  if (!mixChart) {{
    mixChart = new Chart(document.getElementById('mixChart'), {{
      type: 'doughnut',
      data: {{
        labels: ['Wins', 'Draws', 'Losses'],
        datasets: [{{
          data: [d.wins || 0, d.draws || 0, d.losses || 0],
          backgroundColor: ['#5cb87a', '#8d9aab', '#d65a5a'],
          borderWidth: 0,
        }}]
      }},
      options: {{
        animation: false,
        plugins: {{
          legend: {{ position: 'bottom', labels: {{ color: '#8d9aab' }} }}
        }}
      }}
    }});
  }}
  if (!rateChart) {{
    rateChart = new Chart(document.getElementById('rateChart'), {{
      type: 'line',
      data: {{
        labels: s.labels,
        datasets: [{{
          label: 'Score rate',
          data: s.rates,
          borderColor: '#d4a35c',
          backgroundColor: 'rgba(212,163,92,0.14)',
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          tension: 0.2,
        }}]
      }},
      options: {{
        animation: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{
            ticks: {{ color: '#8d9aab', maxTicksLimit: 10 }},
            grid: {{ color: 'rgba(44,53,66,0.7)' }}
          }},
          y: {{
            min: 0, max: 1,
            ticks: {{
              color: '#8d9aab',
              callback: (v) => (v * 100).toFixed(0) + '%'
            }},
            grid: {{ color: 'rgba(44,53,66,0.7)' }}
          }}
        }}
      }}
    }});
  }}
}}

function updateCharts(d) {{
  const key = chartsKey(d);
  if (key === lastChartsKey && eloChart && mixChart && rateChart) return;
  lastChartsKey = key;
  const created = !eloChart || !mixChart || !rateChart;
  if (created) ensureCharts(d);
  const s = seriesFrom(d);
  if (!created) {{
    eloChart.data.labels = s.labels;
    eloChart.data.datasets[0].data = s.eloHi;
    eloChart.data.datasets[1].data = s.eloLo;
    eloChart.data.datasets[2].data = s.elo;
    eloChart.data.datasets[2].pointRadius = s.n < 40 ? 3 : 0;
    mixChart.data.datasets[0].data = [d.wins || 0, d.draws || 0, d.losses || 0];
    rateChart.data.labels = s.labels;
    rateChart.data.datasets[0].data = s.rates;
    eloChart.update('none');
    mixChart.update('none');
    rateChart.update('none');
  }}

  const strip = document.getElementById('strip');
  strip.innerHTML = '';
  s.outcomes.forEach((o) => {{
    const el = document.createElement('span');
    el.className = o;
    el.title = o;
    strip.appendChild(el);
  }});
}}

function applyData(d) {{
  if (!d || d.change_key === lastChangeKey) return;
  lastChangeKey = d.change_key;
  DATA = d;

  document.getElementById('match-line').innerHTML =
    `<strong>${{escapeHtml(d.engine_a)}}</strong> vs <strong>${{escapeHtml(d.engine_b)}}</strong>`
    + ` · ${{escapeHtml(d.mode)}} · depth ${{escapeHtml(d.depth)}}`
    + ` · score from ${{escapeHtml(d.engine_a)}} perspective`;

  let pills = `<span class="pill${{d.status === 'running' ? ' live' : ''}}">${{escapeHtml(d.status)}}</span>`;
  pills += `<span class="pill">${{escapeHtml(d.env_a_eval)}} vs ${{escapeHtml(d.env_b_eval)}}</span>`;
  pills += '<span class="pill">python-chess board</span>';
  pills += `<span class="pill">${{d.sf_available ? ('Stockfish ' + escapeHtml(d.sf_label)) : 'Stockfish off'}}</span>`;
  pills += '<span class="pill">poll 4s · charts on change</span>';
  if (d.live_missing) pills += '<span class="pill warn">live sidecar stale / missing</span>';
  document.getElementById('status-row').innerHTML = pills;

  document.getElementById('board-svg').innerHTML = d.board_svg || '';
  document.getElementById('board-caption').textContent =
    `Game ${{d.game_label}} / ${{d.n_games_live}} · ply ${{d.halfmoves}} · rendered with chess.svg.board`;

  const fill = document.getElementById('eval-white-fill');
  const label = document.getElementById('eval-label');
  const pct = Number(d.sf_pct);
  const sfPct = Number.isFinite(pct) ? pct : 50;
  if (fill) fill.style.height = sfPct.toFixed(2) + '%';
  if (label) {{
    label.textContent = d.sf_available ? d.sf_label : '—';
    label.style.color = sfPct >= 50 ? '#111' : '#f0f0f0';
    label.style.top = sfPct >= 50 ? 'auto' : '6px';
    label.style.bottom = sfPct >= 50 ? '6px' : 'auto';
  }}
  const evalMeta = document.getElementById('eval-meta');
  if (d.sf_available) {{
    evalMeta.textContent =
      'Stockfish d' + d.sf_depth + ' · ' + d.sf_label
      + (d.sf_best && d.sf_best !== '—' ? (' · best ' + d.sf_best) : '')
      + (d.sf_pv ? (' · ' + d.sf_pv) : '');
  }} else {{
    evalMeta.textContent =
      'Stockfish unavailable — install stockfish or set ANCE_STOCKFISH';
  }}

  document.getElementById('game-title').textContent = 'Game ' + d.game_label;
  document.getElementById('name-black').textContent = d.black || '—';
  document.getElementById('name-white').textContent = d.white || '—';
  document.getElementById('tag-black').textContent =
    'Black · ' + JSON.stringify(d.black_env || {{}});
  document.getElementById('tag-white').textContent =
    'White · ' + JSON.stringify(d.white_env || {{}});
  document.getElementById('seat-black').className =
    'seat' + (d.turn === 'black' ? ' active' : '');
  document.getElementById('seat-white').className =
    'seat' + (d.turn === 'white' ? ' active' : '');

  const check = d.in_check ? '<span class="badge check">CHECK</span>' : '';
  const thinkLive = d.thinking ? ' · <span id="think-live">searching…</span>' : '';
  const note = d.live_note ? (' · ' + escapeHtml(d.live_note)) : '';
  document.getElementById('thinking').innerHTML =
    `Thinking: <strong>${{escapeHtml(d.thinker)}}</strong> (${{escapeHtml(d.turn)}})${{check}}${{thinkLive}}<br/>`
    + `Last: <strong style="color:var(--ink)">${{escapeHtml(d.last_san)}}</strong>`
    + ` · think ${{escapeHtml(d.last_think_s)}}`
    + ` · material ${{escapeHtml(d.material_balance)}}`
    + note;

  document.getElementById('meta-material').textContent =
    Number(d.material_white || 0).toFixed(0) + ' / ' + Number(d.material_black || 0).toFixed(0);
  document.getElementById('meta-pieces').textContent = d.piece_count;
  document.getElementById('meta-opening').textContent = d.opening_index;
  document.getElementById('meta-updated').textContent = d.live_updated || '—';
  document.getElementById('moves').innerHTML = d.moves_html || '';
  document.getElementById('fen').textContent = 'FEN ' + (d.fen || '');

  document.getElementById('progress-bar').style.width =
    Number(d.pct || 0).toFixed(3) + '%';
  document.getElementById('progress-left').textContent =
    `${{d.n_done || 0}} / ${{d.n_target || 0}} games (${{Number(d.pct || 0).toFixed(1)}}%)`;
  document.getElementById('progress-right').textContent =
    `elapsed ${{d.elapsed_hms}} · ETA ${{d.eta_hms}} · ~${{Number(d.pace_s || 0).toFixed(0)}}s/game`;

  document.getElementById('stat-elo').textContent = d.elo_fmt || '—';
  document.getElementById('stat-elo-hint').textContent =
    `95% CI [${{d.elo_lo_fmt}}, ${{d.elo_hi_fmt}}]`;
  document.getElementById('stat-rate').textContent = d.score_rate_pct || '—';
  document.getElementById('stat-wdl').textContent =
    `W–D–L = ${{d.wins || 0}}–${{d.draws || 0}}–${{d.losses || 0}}`;
  const d12 = document.getElementById('stat-d12');
  d12.textContent = d.d12_pass ? 'PASS' : 'OPEN';
  d12.style.color = d.d12_pass ? 'var(--win)' : 'var(--warn)';
  document.getElementById('stat-sample').textContent = d.n_done || 0;
  document.getElementById('stat-sample-hint').textContent =
    `target ${{d.n_target || 0}} · depth ${{d.depth}}`;

  document.getElementById('footer').innerHTML =
    `Checkpoint: ${{escapeHtml(d.source)}}<br/>`
    + `Live: ${{escapeHtml(d.live_source || '—')}} · generated ${{escapeHtml(d.generated_at)}} UTC<br/>`
    + `<code>python -m ance.tools.gauntlet_dashboard --serve --open</code>`;

  clockState = {{
    turn: d.turn || 'white',
    thinking: !!d.thinking,
    think_elapsed_s: d.think_elapsed_s || 0,
    white_clock_s: d.white_clock_s || 0,
    black_clock_s: d.black_clock_s || 0,
  }};
  clockPageLoaded = Date.now();
  updateCharts(d);
}}

function paintClocks() {{
  const drift = clockState.thinking ? (Date.now() - clockPageLoaded) / 1000 : 0;
  let w = Number(clockState.white_clock_s) || 0;
  let b = Number(clockState.black_clock_s) || 0;
  if (clockState.thinking) {{
    if (clockState.turn === 'white') w = Math.max(0, w - drift);
    else b = Math.max(0, b - drift);
  }}
  const cw = document.getElementById('clock-white');
  const cb = document.getElementById('clock-black');
  if (cw) cw.textContent = fmtClock(w);
  if (cb) cb.textContent = fmtClock(b);
  const tl = document.getElementById('think-live');
  if (tl && clockState.thinking) {{
    tl.textContent = 'thinking ' + (Number(clockState.think_elapsed_s || 0) + drift).toFixed(1) + 's';
  }}
  requestAnimationFrame(paintClocks);
}}

async function pollOnce() {{
  try {{
    const res = await fetch('/api.json', {{ cache: 'no-store' }});
    if (!res.ok) return;
    const next = await res.json();
    applyData(next);
  }} catch (_) {{
    // file:// or transient errors — keep current view
  }}
}}

applyData(DATA);
paintClocks();

const canPoll = location.protocol === 'http:' || location.protocol === 'https:';
if (canPoll) {{
  setInterval(pollOnce, 4000);
}} else {{
  const meta = document.createElement('meta');
  meta.httpEquiv = 'refresh';
  meta.content = '4';
  document.head.appendChild(meta);
}}
</script>
</body>
</html>
"""
    return html, payload



def generate(
    checkpoint_path: Path,
    out_path: Path,
    *,
    live_path: Path | None = None,
    board_size: int = 560,
    analyzer: StockfishAnalyzer | None = None,
) -> dict:
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    series = build_series(list(checkpoint.get("games") or []))

    live: dict | None = None
    if live_path is not None and live_path.exists():
        live = json.loads(live_path.read_text(encoding="utf-8"))

    fen = (live or {}).get("fen") or chess.STARTING_FEN
    last_uci = (live or {}).get("last_uci")
    board_svg = render_board_svg(fen, last_uci, size=board_size)

    sf_eval: dict | None = None
    if analyzer is not None:
        try:
            sf_eval = analyzer.evaluate(fen).as_dict()
        except Exception as exc:  # noqa: BLE001
            sf_eval = {
                "label": "err",
                "white_win_pct": 50.0,
                "depth": 0,
                "pv_san": [],
                "bestmove_uci": None,
                "error": f"{type(exc).__name__}: {exc}",
            }

    html, payload = render_html(
        checkpoint,
        series,
        live,
        board_svg,
        checkpoint_path,
        live_path,
        sf_eval=sf_eval,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    # Standalone SVG for Quick Look / training tooling reuse.
    svg_path = out_path.with_name(out_path.stem + "-board.svg")
    svg_path.write_text(board_svg, encoding="utf-8")

    agg = checkpoint.get("aggregate") or {}
    return {
        "out": str(out_path),
        "svg": str(svg_path),
        "n_done": series["n"],
        "status": checkpoint.get("status"),
        "aggregate": agg,
        "game_index": (live or {}).get("game_index"),
        "halfmoves": (live or {}).get("halfmoves"),
        "last_san": (live or {}).get("last_san"),
        "sf_eval": sf_eval,
        "payload": payload,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    phase = root / ".planning/phases/05-nnue-swap-in-elo-gauntlet"
    default_ckpt = phase / "05-gauntlet-checkpoint.json"
    default_live = phase / "05-gauntlet-live.json"
    default_out = phase / "05-gauntlet-dashboard.html"

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, default=default_ckpt)
    p.add_argument("--live", type=Path, default=default_live)
    p.add_argument("--out", type=Path, default=default_out)
    p.add_argument("--size", type=int, default=560)
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=4.0)
    p.add_argument("--serve", action="store_true",
                   help="HTTP server: HTML shell + /api.json poll (preferred)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--open", action="store_true")
    p.add_argument(
        "--stockfish",
        default="auto",
        help="Stockfish binary path, 'auto', or 'off'",
    )
    p.add_argument("--sf-depth", type=int, default=14)
    p.add_argument("--sf-movetime-ms", type=int, default=0,
                   help="If >0, use movetime instead of depth")
    args = p.parse_args(argv)

    analyzer: StockfishAnalyzer | None = None
    if args.stockfish != "off":
        binary = None if args.stockfish == "auto" else args.stockfish
        if find_stockfish(binary) is None:
            print("warning: Stockfish not found — eval bar disabled")
        else:
            analyzer = StockfishAnalyzer(
                binary,
                depth=args.sf_depth,
                movetime_ms=args.sf_movetime_ms or None,
            )

    try:
        if args.serve:
            return _serve(
                checkpoint=args.checkpoint,
                live=args.live,
                out=args.out,
                board_size=args.size,
                host=args.host,
                port=args.port,
                open_browser=args.open,
                analyzer=analyzer,
            )

        opened = False
        while True:
            if not args.checkpoint.exists():
                print(f"waiting for checkpoint: {args.checkpoint}")
            else:
                info = generate(
                    args.checkpoint,
                    args.out,
                    live_path=args.live if args.live.exists() else None,
                    board_size=args.size,
                    analyzer=analyzer,
                )
                agg = info["aggregate"] or {}
                sf = info.get("sf_eval") or {}
                print(
                    f"wrote {info['out']}  "
                    f"games={info['n_done']} status={info['status']} "
                    f"WDL={agg.get('wins')}-{agg.get('draws')}-{agg.get('losses')} "
                    f"elo={agg.get('elo')} "
                    f"live_game={info.get('game_index')} "
                    f"ply={info.get('halfmoves')} last={info.get('last_san')} "
                    f"sf={sf.get('label', '—')}"
                )
                if args.open and not opened:
                    webbrowser.open(args.out.resolve().as_uri())
                    opened = True
            if not args.watch:
                break
            time.sleep(args.interval)
        return 0
    finally:
        if analyzer is not None:
            analyzer.close()


def _serve(
    *,
    checkpoint: Path,
    live: Path,
    out: Path,
    board_size: int,
    host: str,
    port: int,
    open_browser: bool,
    analyzer: StockfishAnalyzer | None = None,
) -> int:
    """Serve HTML shell once; clients poll /api.json every 4s (charts on change)."""

    class Handler(BaseHTTPRequestHandler):
        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except Exception as exc:  # noqa: BLE001
                print(f"request error: {type(exc).__name__}: {exc}")

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            want_api = path in ("/api.json", "/api")
            want_html = path in ("/", "/index.html", "/dashboard.html")
            if not want_api and not want_html:
                # favicon / chrome probes / anything else - never send_error
                # with non-latin-1 messages (crashes the handler).
                self.send_response(204)
                self.end_headers()
                return
            if not checkpoint.exists():
                if want_api:
                    body = b'{"status":"waiting","change_key":"waiting","n_done":0}'
                    ctype = "application/json; charset=utf-8"
                else:
                    body = (
                        "<html><body style='font-family:monospace;background:#12151a;"
                        "color:#eef2f6;padding:2rem'>"
                        f"Waiting for checkpoint: {checkpoint}</body></html>"
                    ).encode()
                    ctype = "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            try:
                info = generate(
                    checkpoint,
                    out,
                    live_path=live if live.exists() else None,
                    board_size=board_size,
                    analyzer=analyzer,
                )
                if want_api:
                    body = json.dumps(
                        info["payload"], allow_nan=False
                    ).encode("utf-8")
                    ctype = "application/json; charset=utf-8"
                else:
                    body = out.read_bytes()
                    ctype = "text/html; charset=utf-8"
            except Exception as exc:  # noqa: BLE001 - keep server alive
                msg = f"dashboard generate failed: {type(exc).__name__}: {exc}"
                print(msg)
                if want_api:
                    body = json.dumps(
                        {"error": msg, "change_key": f"error:{msg}"}
                    ).encode("utf-8")
                    ctype = "application/json; charset=utf-8"
                else:
                    body = (
                        "<html><body style='font-family:monospace;background:#12151a;"
                        f"color:#eef2f6;padding:2rem'>{msg}</body></html>"
                    ).encode()
                    ctype = "text/html; charset=utf-8"
                self.send_response(500)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            agg = info.get("aggregate") or {}
            sf = (info.get("sf_eval") or {}).get("label", "—")
            kind = "api" if want_api else "html"
            print(
                f"GET /{kind} games={info['n_done']} "
                f"live={info.get('game_index')} ply={info.get('halfmoves')} "
                f"last={info.get('last_san')} "
                f"WDL={agg.get('wins')}-{agg.get('draws')}-{agg.get('losses')} "
                f"sf={sf}"
            )

        def log_message(self, fmt: str, *a: object) -> None:
            return  # quiet; we print our own line above

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"ANCE dashboard at {url}")
    print(f"  checkpoint: {checkpoint}")
    print(f"  live:       {live}")
    print("  /api.json polled every 4s; charts update only when WDL/n_done changes")
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
