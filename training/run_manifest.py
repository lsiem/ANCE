"""Shared provenance log for reproducible training runs (D-08)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def record_event(manifest_path: str, **fields: Any) -> None:
    path = Path(manifest_path)
    events: list[dict[str, Any]]
    if path.exists():
        events = json.loads(path.read_text())
    else:
        events = []

    events.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            **fields,
        }
    )
    path.write_text(json.dumps(events, indent=2))
