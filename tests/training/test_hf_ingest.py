"""Tests for the Hugging Face Lichess eval-dataset ingest (offline only)."""

from __future__ import annotations

import zlib

import pytest

pytest.importorskip("pyarrow")

from training.data.hf_ingest import iter_parquet_samples, row_to_sample

_WHITE_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_BLACK_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _row(
    fen: str = _WHITE_FEN,
    depth: int | None = 30,
    knodes: int | None = 5,
    cp: int | None = 20,
    mate: int | None = None,
) -> dict:
    return {"fen": fen, "line": "e2e4", "depth": depth, "knodes": knodes, "cp": cp, "mate": mate}


class TestSignConvention:
    def test_black_to_move_cp_is_negated(self) -> None:
        sample = row_to_sample(_row(fen=_BLACK_FEN, cp=150))
        assert sample is not None
        assert sample["cp"] == -150.0

    def test_white_to_move_cp_is_unchanged(self) -> None:
        sample = row_to_sample(_row(fen=_WHITE_FEN, cp=150))
        assert sample is not None
        assert sample["cp"] == 150.0


class TestMateMapping:
    def test_mate_positive_white_to_move(self) -> None:
        sample = row_to_sample(_row(fen=_WHITE_FEN, cp=None, mate=3))
        assert sample is not None
        assert sample["cp"] == 99_997.0

    def test_mate_positive_black_to_move(self) -> None:
        sample = row_to_sample(_row(fen=_BLACK_FEN, cp=None, mate=3))
        assert sample is not None
        assert sample["cp"] == -99_997.0

    def test_mate_negative_white_to_move(self) -> None:
        sample = row_to_sample(_row(fen=_WHITE_FEN, cp=None, mate=-2))
        assert sample is not None
        assert sample["cp"] == -99_998.0


class TestQualityFilter:
    def test_depth_alone_passes(self) -> None:
        assert row_to_sample(_row(depth=25, knodes=10), min_depth=20, min_knodes=1000) is not None

    def test_knodes_alone_passes_or_semantics(self) -> None:
        assert row_to_sample(_row(depth=10, knodes=5000), min_depth=20, min_knodes=1000) is not None

    def test_both_below_thresholds_rejected(self) -> None:
        assert row_to_sample(_row(depth=10, knodes=10), min_depth=20, min_knodes=1000) is None

    def test_both_none_rejected(self) -> None:
        assert row_to_sample(_row(depth=None, knodes=None), min_depth=20, min_knodes=1000) is None


class TestSkipRow:
    def test_no_cp_and_no_mate_is_skipped(self) -> None:
        assert row_to_sample(_row(cp=None, mate=None)) is None

    def test_short_fen_is_skipped(self) -> None:
        assert row_to_sample(_row(fen="onlyonefield")) is None

    @pytest.mark.parametrize("n_buckets", [0, -1])
    def test_non_positive_bucket_count_raises(self, n_buckets: int) -> None:
        with pytest.raises(ValueError, match="n_buckets must be a positive integer"):
            row_to_sample(_row(), n_buckets=n_buckets)


class TestPseudoGameId:
    def test_same_fen_same_game_id_and_deterministic_crc32(self) -> None:
        first = row_to_sample(_row())
        second = row_to_sample(_row())
        assert first is not None and second is not None
        assert first["game_id"] == second["game_id"]
        # Pinned to crc32 bucketing — NOT the per-process-salted built-in hash().
        expected_bucket = zlib.crc32(_WHITE_FEN.encode("utf-8")) % 1000
        assert first["game_id"] == f"hf-{expected_bucket:04d}"

    def test_game_id_form(self) -> None:
        sample = row_to_sample(_row())
        assert sample is not None
        assert sample["game_id"].startswith("hf-")
        suffix = sample["game_id"][3:]
        assert suffix == suffix.zfill(4)
        assert suffix.isdigit()

    def test_multiple_buckets_over_many_fens(self) -> None:
        game_ids = set()
        for i in range(200):
            fen = f"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 {i + 1}"
            sample = row_to_sample(_row(fen=fen), n_buckets=8)
            assert sample is not None
            game_ids.add(sample["game_id"])
        assert len(game_ids) > 1


class TestParquetStreaming:
    _ROWS = [
        # passes via depth; white to move -> +20
        {"fen": _WHITE_FEN, "line": "e2e4", "depth": 30, "knodes": 5, "cp": 20, "mate": None},
        # passes via depth; black to move -> -150
        {"fen": _BLACK_FEN, "line": "e7e5", "depth": 30, "knodes": 5, "cp": 150, "mate": None},
        # rejected: below both thresholds
        {
            "fen": "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1",
            "line": "g8f6",
            "depth": 5,
            "knodes": 5,
            "cp": 10,
            "mate": None,
        },
        # passes via depth; mate mapping, white to move -> +99_997
        {
            "fen": "rnbqkbnr/ppppp1pp/8/5p2/8/4P3/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "line": "d1h5",
            "depth": 30,
            "knodes": None,
            "cp": None,
            "mate": 3,
        },
        # skipped: neither cp nor mate
        {
            "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
            "line": "g1f3",
            "depth": 30,
            "knodes": 5,
            "cp": None,
            "mate": None,
        },
    ]

    def _write_parquet(self, tmp_path) -> str:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(self._ROWS)
        path = tmp_path / "shard.parquet"
        pq.write_table(table, str(path))
        return str(path)

    def test_yields_filtered_transformed_samples(self, tmp_path) -> None:
        path = self._write_parquet(tmp_path)
        samples = list(
            iter_parquet_samples(path, min_depth=20, min_knodes=1000, n_buckets=1000)
        )
        assert [s["cp"] for s in samples] == [20.0, -150.0, 99_997.0]
        assert all(s["source"] == "lichess-hf" for s in samples)
        assert all(s["game_result"] is None for s in samples)

    def test_max_positions_cap_mid_file(self, tmp_path) -> None:
        path = self._write_parquet(tmp_path)
        samples = list(
            iter_parquet_samples(
                path, min_depth=20, min_knodes=1000, n_buckets=1000, max_positions=2
            )
        )
        assert len(samples) == 2
        assert [s["cp"] for s in samples] == [20.0, -150.0]
