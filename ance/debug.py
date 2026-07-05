"""Stderr-only diagnostic channel (D-18).

Off by default, toggled on via the UCI `debug on`/`debug off` command or the
`ANCE_DEBUG` environment variable. Never writes to stdout -- the protocol
stream (`ance/uci/protocol.py`) must stay clean for the GUI/gauntlet parsing
it, so diagnostics live exclusively on stderr, a local-only sink (T-01-05:
information disclosure is accepted here since stderr never leaves the local
process pipe).
"""

from __future__ import annotations

import os
import sys

_enabled: bool = bool(os.environ.get("ANCE_DEBUG"))


def set_enabled(value: bool) -> None:
    global _enabled
    _enabled = value


def log(msg: str) -> None:
    if _enabled:
        print(msg, file=sys.stderr, flush=True)
