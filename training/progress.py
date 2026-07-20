"""Optional tqdm progress helpers for the offline training pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, TypeVar

T = TypeVar("T")

try:
    from tqdm import tqdm as _tqdm
except ImportError:  # pragma: no cover - tqdm is a project dep
    _tqdm = None  # type: ignore[assignment]


def progress_bar(
    iterable: Iterable[T] | None = None,
    *,
    total: int | None = None,
    desc: str | None = None,
    unit: str = "it",
    leave: bool = True,
    initial: int = 0,
    **kwargs: Any,
):
    """Return a tqdm bar, or a no-op stand-in when tqdm is unavailable."""
    if _tqdm is not None:
        if iterable is None:
            return _tqdm(
                total=total,
                desc=desc,
                unit=unit,
                leave=leave,
                initial=initial,
                **kwargs,
            )
        return _tqdm(
            iterable,
            total=total,
            desc=desc,
            unit=unit,
            leave=leave,
            initial=initial,
            **kwargs,
        )

    class _NoopBar:
        def __init__(self) -> None:
            self.n = initial

        def update(self, n: int = 1) -> None:
            self.n += n

        def set_postfix(self, *args: Any, **kwargs: Any) -> None:
            return None

        def close(self) -> None:
            return None

        def __enter__(self) -> _NoopBar:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def __iter__(self) -> Iterator[T]:
            assert iterable is not None
            for item in iterable:
                yield item

    return _NoopBar()
