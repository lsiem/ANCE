"""Live chessboard viewer powered by python-chess SVG rendering.

Uses ``chess.svg.board`` (the standard python-chess / "pychess" board artwork)
with last-move and check highlighting, and optionally writes a PNG via CairoSVG.

  .venv/bin/python -m ance.tools.gauntlet_board --open --watch
  .venv/bin/python -m ance.tools.gauntlet_board --png   # also write 05-live-board.png
"""

from __future__ import annotations

import argparse
import json
import time
import webbrowser
from pathlib import Path

import chess
import chess.svg

try:
    import cairosvg
except ImportError:  # pragma: no cover - optional for PNG export
    cairosvg = None  # type: ignore[assignment]


def render_board_svg(fen: str, last_uci: str | None = None, size: int = 560) -> str:
    """Render a position with python-chess's built-in SVG board artwork."""
    board = chess.Board(fen)
    lastmove = None
    if last_uci:
        try:
            lastmove = chess.Move.from_uci(last_uci)
        except ValueError:
            lastmove = None

    check_square = board.king(board.turn) if board.is_check() else None
    return chess.svg.board(
        board=board,
        lastmove=lastmove,
        check=check_square,
        size=size,
        coordinates=True,
    )


def _format_moves(sans: list[str]) -> str:
    if not sans:
        return "<div class='muted'>Waiting for first move…</div>"
    rows: list[str] = []
    for i in range(0, len(sans), 2):
        num = i // 2 + 1
        white = sans[i]
        black = sans[i + 1] if i + 1 < len(sans) else ""
        rows.append(
            f"<div class='ply'><span class='n'>{num}.</span> "
            f"<span class='w'>{white}</span> <span class='b'>{black}</span></div>"
        )
    return "\n".join(rows)


def render_html(live: dict, source: Path, board_svg: str) -> str:
    white = live.get("white", "?")
    black = live.get("black", "?")
    turn = live.get("turn", "?")
    game_index = live.get("game_index", "?")
    n_games = live.get("n_games", "?")
    last_san = live.get("last_san") or "—"
    halfmoves = live.get("halfmoves", 0)
    updated = live.get("updated_utc", "—")
    fen = live.get("fen") or chess.STARTING_FEN
    thinker = white if turn == "white" else black
    game_label = (
        f"{int(game_index) + 1}" if isinstance(game_index, int) else str(game_index)
    )
    moves_block = _format_moves(list(live.get("san_moves") or []))
    check_note = " · CHECK" if chess.Board(fen).is_check() else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta http-equiv="refresh" content="2" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>ANCE live board — game {game_label}</title>
<style>
  :root {{
    --bg: #0e141c;
    --panel: #182230;
    --ink: #f2f6fb;
    --muted: #9aabbc;
    --line: #2a3a4d;
    --accent: #3dd6c6;
    --warm: #e8a54b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    color: var(--ink);
    font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    background:
      radial-gradient(1000px 520px at 8% -8%, #163532 0%, transparent 55%),
      radial-gradient(800px 420px at 100% 0%, #3a2a14 0%, transparent 50%),
      var(--bg);
  }}
  .wrap {{
    max-width: 1040px;
    margin: 0 auto;
    padding: 24px 18px 40px;
    display: grid;
    grid-template-columns: auto minmax(260px, 1fr);
    gap: 22px;
    align-items: start;
  }}
  @media (max-width: 860px) {{
    .wrap {{ grid-template-columns: 1fr; }}
  }}
  .brand {{
    grid-column: 1 / -1;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--accent);
    font-size: 12px;
  }}
  h1 {{
    grid-column: 1 / -1;
    margin: 0;
    font-size: clamp(1.4rem, 2.5vw, 1.85rem);
    font-weight: 600;
  }}
  .board-panel {{
    background: var(--panel);
    border: 1px solid var(--line);
    padding: 14px;
    width: fit-content;
    box-shadow: 0 18px 40px rgba(0,0,0,0.35);
  }}
  .board-panel svg {{
    display: block;
    max-width: min(560px, 92vw);
    height: auto;
  }}
  .side {{
    background: var(--panel);
    border: 1px solid var(--line);
    padding: 16px;
    min-height: 560px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .players {{ display: grid; gap: 8px; }}
  .seat {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border: 1px solid var(--line);
    background: #101821;
  }}
  .seat.active {{
    border-color: color-mix(in srgb, var(--accent) 55%, var(--line));
    box-shadow: inset 3px 0 0 var(--accent);
  }}
  .seat .name {{ font-weight: 600; }}
  .seat .tag {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px;
    color: var(--muted);
  }}
  .meta {{
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 12px;
    color: var(--muted);
    line-height: 1.6;
  }}
  .meta strong {{ color: var(--ink); }}
  .check {{ color: #ff6b6b; font-weight: 700; }}
  .moves {{
    flex: 1;
    overflow: auto;
    border-top: 1px solid var(--line);
    padding-top: 10px;
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 13px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 14px;
    max-height: 300px;
  }}
  .ply .n {{ color: var(--muted); }}
  .ply .w {{ color: var(--ink); }}
  .ply .b {{ color: var(--warm); }}
  .muted {{ color: var(--muted); }}
  footer {{
    grid-column: 1 / -1;
    color: var(--muted);
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 11px;
    word-break: break-all;
  }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="brand">ANCE · python-chess SVG board · refresh 2s</div>
    <h1>Game {game_label} / {n_games}</h1>
    <div class="board-panel">{board_svg}</div>
    <div class="side">
      <div class="players">
        <div class="seat {'active' if turn == 'black' else ''}">
          <div>
            <div class="name">{black}</div>
            <div class="tag">Black · {json.dumps(live.get('black_env') or {})}</div>
          </div>
          <div class="tag">▲</div>
        </div>
        <div class="seat {'active' if turn == 'white' else ''}">
          <div>
            <div class="name">{white}</div>
            <div class="tag">White · {json.dumps(live.get('white_env') or {})}</div>
          </div>
          <div class="tag">▼</div>
        </div>
      </div>
      <div class="meta">
        Thinking: <strong style="color:var(--accent)">{thinker}</strong> ({turn})
        <span class="check">{check_note}</span><br/>
        Last move: <strong>{last_san}</strong> · ply {halfmoves}<br/>
        Mode: {live.get('mode')} / depth={live.get('search_depth')}<br/>
        Updated: {updated}
      </div>
      <div class="moves">{moves_block}</div>
    </div>
    <footer>Source: {source}<br/>FEN: {fen}</footer>
  </div>
</body>
</html>
"""


def write_png(svg: str, png_path: Path) -> None:
    if cairosvg is None:
        raise RuntimeError("cairosvg is not installed; pip install cairosvg")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_path))


def generate(
    live_path: Path,
    out_path: Path,
    *,
    png_path: Path | None = None,
    size: int = 560,
) -> dict:
    live = json.loads(live_path.read_text(encoding="utf-8"))
    fen = live.get("fen") or chess.STARTING_FEN
    svg = render_board_svg(fen, live.get("last_uci"), size=size)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(live, live_path, svg), encoding="utf-8")
    # Keep a standalone SVG next to the HTML for tooling / Quick Look.
    svg_path = out_path.with_suffix(".svg")
    svg_path.write_text(svg, encoding="utf-8")
    if png_path is not None:
        write_png(svg, png_path)
    return {
        "out": str(out_path),
        "svg": str(svg_path),
        "png": str(png_path) if png_path else None,
        "game_index": live.get("game_index"),
        "halfmoves": live.get("halfmoves"),
        "fen": fen,
        "turn": live.get("turn"),
        "last_san": live.get("last_san"),
    }


def seed_from_checkpoint(checkpoint: Path, live_path: Path) -> None:
    """Seed a live file from the next unfinished game's opening (pre-resume)."""
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    n = len(data.get("games") or [])
    params = data["parameters"]
    openings = params["openings"]
    opening_index = (n // 2) % len(openings)
    a_is_white = n % 2 == 0
    a = params["engine_a"]
    b = params["engine_b"]
    fen = openings[opening_index]
    payload = {
        "game_index": n,
        "n_games": params["n_games"],
        "opening_index": opening_index,
        "opening_fen": fen,
        "a_is_white": a_is_white,
        "white": a["name"] if a_is_white else b["name"],
        "black": b["name"] if a_is_white else a["name"],
        "white_env": dict((a if a_is_white else b).get("env") or {}),
        "black_env": dict((b if a_is_white else a).get("env") or {}),
        "search_depth": params.get("search_depth"),
        "mode": params.get("mode"),
        "fen": fen,
        "turn": "white" if chess.Board(fen).turn == chess.WHITE else "black",
        "halfmoves": 0,
        "san_moves": [],
        "last_uci": None,
        "last_san": None,
        "is_game_over": False,
        "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "opening seed — waiting for live ply updates",
    }
    live_path.parent.mkdir(parents=True, exist_ok=True)
    live_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    phase = root / ".planning/phases/05-nnue-swap-in-elo-gauntlet"
    default_live = phase / "05-gauntlet-live.json"
    default_out = phase / "05-gauntlet-board.html"
    default_ckpt = phase / "05-gauntlet-checkpoint.json"
    default_png = phase / "05-live-board.png"

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", type=Path, default=default_live)
    p.add_argument("--out", type=Path, default=default_out)
    p.add_argument("--checkpoint", type=Path, default=default_ckpt)
    p.add_argument("--png", nargs="?", const=str(default_png), default=None)
    p.add_argument("--size", type=int, default=560)
    p.add_argument("--seed", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--open", action="store_true")
    args = p.parse_args(argv)

    if args.seed or not args.live.exists():
        if args.checkpoint.exists():
            seed_from_checkpoint(args.checkpoint, args.live)
            print(f"seeded {args.live}")
        else:
            print(f"missing checkpoint: {args.checkpoint}")
            return 1

    png_path = Path(args.png) if args.png else None
    opened = False
    while True:
        if args.live.exists():
            info = generate(
                args.live,
                args.out,
                png_path=png_path,
                size=args.size,
            )
            print(
                f"wrote {info['out']}  game={info['game_index']} "
                f"ply={info['halfmoves']} last={info['last_san']} turn={info['turn']}"
                + (f" png={info['png']}" if info["png"] else "")
            )
            if args.open and not opened:
                webbrowser.open(args.out.resolve().as_uri())
                opened = True
        else:
            print(f"waiting for {args.live}")
        if not args.watch:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
