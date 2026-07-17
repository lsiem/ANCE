"""Merge labeled sample streams and deduplicate by FEN."""

from __future__ import annotations


def merge_and_dedup(streams: list[list[dict]]) -> list[dict]:
    """Concatenate sample lists and keep the first occurrence per FEN.

    Tie-break rule: when the same FEN appears in multiple streams, the
    first-seen sample (by stream order, then row order) is kept.
    """
    merged: list[dict] = []
    seen_fens: set[str] = set()
    for stream in streams:
        for sample in stream:
            fen = sample["fen"]
            if fen in seen_fens:
                continue
            seen_fens.add(fen)
            merged.append(sample)
    return merged
