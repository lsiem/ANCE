"""Hand-written UCI protocol I/O -- reader/dispatch loop, parsing, and
response formatting. `chess.engine`/`chess.uci` are never used here (D-00c):
ANCE speaks UCI on its own stdin/stdout as the engine, not as a client.
"""
