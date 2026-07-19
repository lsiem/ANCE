"""Hugging Face ``Lichess/chess-position-evaluations`` ingest (pre-labeled NNUE data).

Streams parquet shards of the Lichess evaluation dataset (395M positions,
CC0-1.0) and converts rows to the pipeline's STM-relative sample dict
contract. Lichess publishes cp/mate values white-relative; ``row_to_sample``
negates the score when the FEN side-to-move is black, mirroring
``training.data.lichess_ingest.extract_samples``.

Pseudo game ids: the dataset has no game ids, but ``split_by_game``
partitions train/val by ``game_id``. Each FEN is assigned a stable bucket via
``zlib.crc32(fen) % n_buckets`` formatted as ``"hf-NNNN"``. crc32 is used
instead of the built-in ``hash()`` because ``hash()`` is salted per process
(PYTHONHASHSEED), which would break resume determinism and split stability
across runs. Because the bucket is a pure function of the full FEN, identical
FENs always share a game_id, so ``assert_no_fen_leakage`` holds by
construction.

``pyarrow`` and ``huggingface_hub`` imports are lazy (inside the functions
that use them) so importing this module — and therefore
``training.run_pipeline`` — never requires the ``hf-ingest`` extras.
"""

from __future__ import annotations

import time
import zlib
from collections.abc import Iterator

# Mirrors training.run_pipeline._MATE_SCORE / _cp_from_label arithmetic.
# Not imported from run_pipeline: run_pipeline imports training.data.*,
# so importing it here would be circular.
_MATE_SCORE = 100_000

_HF_DEFAULT_REPO = "Lichess/chess-position-evaluations"
_BATCH_SIZE = 65_536
_COLUMNS = ["fen", "depth", "knodes", "cp", "mate"]


def row_to_sample(
    row: dict,
    *,
    min_depth: int = 20,
    min_knodes: int = 1000,
    n_buckets: int = 1000,
    mate_score: int = _MATE_SCORE,
) -> dict | None:
    """Convert one dataset row to a pipeline sample dict, or None to skip.

    Quality filter uses OR semantics: a row is kept iff its depth OR its
    knodes meets the corresponding threshold (None values never pass).
    """
    if n_buckets <= 0:
        raise ValueError(f"n_buckets must be a positive integer, got {n_buckets}")

    depth = row.get("depth")
    knodes = row.get("knodes")
    depth_ok = depth is not None and depth >= min_depth
    knodes_ok = knodes is not None and knodes >= min_knodes
    if not (depth_ok or knodes_ok):
        return None

    cp = row.get("cp")
    if cp is not None:
        score = float(cp)
    else:
        mate = row.get("mate")
        if mate is None:
            return None
        mate_n = int(mate)
        if mate_n > 0:
            score = float(mate_score - mate_n)
        else:
            score = float(-mate_score - mate_n)

    fen = row.get("fen")
    if not fen:
        return None
    fields = fen.split()
    if len(fields) < 2:
        return None
    if fields[1] == "b":
        # Lichess evals are white-relative; the sample contract is STM-relative.
        score = -score

    bucket = zlib.crc32(fen.encode("utf-8")) % n_buckets
    return {
        "fen": fen,
        "cp": float(score),
        "game_result": None,
        "game_id": f"hf-{bucket:04d}",
        "source": "lichess-hf",
    }


def iter_parquet_samples(
    path: str,
    *,
    min_depth: int = 20,
    min_knodes: int = 1000,
    n_buckets: int = 1000,
    max_positions: int | None = None,
    deadline_monotonic: float | None = None,
) -> Iterator[dict]:
    """Stream filtered+transformed samples from one local parquet shard.

    Iterates record batches so peak RAM stays small — a whole shard is never
    materialized (24 GB unified-memory constraint). The deadline is checked
    per record batch so a shard whose rows all fail the quality filter still
    respects the run's time bound.
    """
    import pyarrow.parquet as pq

    yielded = 0
    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=_BATCH_SIZE, columns=_COLUMNS):
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            return
        for row in batch.to_pylist():
            sample = row_to_sample(
                row,
                min_depth=min_depth,
                min_knodes=min_knodes,
                n_buckets=n_buckets,
            )
            if sample is None:
                continue
            yield sample
            yielded += 1
            if max_positions is not None and yielded >= max_positions:
                return


def iter_hf_samples(
    repo_id: str = _HF_DEFAULT_REPO,
    *,
    max_positions: int,
    min_depth: int = 20,
    min_knodes: int = 1000,
    n_buckets: int = 1000,
    deadline_monotonic: float | None = None,
) -> Iterator[dict]:
    """Stream samples from the Hugging Face dataset, shard by shard.

    Downloads parquet shards lazily (HF cache handles reuse) and stops as
    soon as ``max_positions`` samples have been yielded, so later shards are
    never downloaded — the ~42 GB dataset must never be pulled wholesale.
    ``deadline_monotonic`` is checked before every shard download (and per
    batch inside each shard) so an unsatisfiable filter cannot keep pulling
    shards past the run's time bound.
    """
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    shard_names = sorted(
        name
        for name in api.list_repo_files(repo_id, repo_type="dataset")
        if name.endswith(".parquet")
    )
    remaining = max_positions
    for filename in shard_names:
        if remaining <= 0:
            return
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            return
        local_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
        )
        for sample in iter_parquet_samples(
            local_path,
            min_depth=min_depth,
            min_knodes=min_knodes,
            n_buckets=n_buckets,
            max_positions=remaining,
            deadline_monotonic=deadline_monotonic,
        ):
            yield sample
            remaining -= 1
