"""Unit tests for :class:`app.tools.data_loader.DataLoader` (Phase 1, Developer B).

Covers: successful load, missing file, missing required columns, malformed
values, an empty (all-malformed) dataset, dedup, and deterministic output shape.
Uses small CSV fixtures written to ``tmp_path`` — no dependency on the real
sample/synthetic dataset (which doesn't exist yet).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.enums import ExecutionStatus, ToolName
from app.schemas import Context
from app.tools.data_loader import REQUIRED_COLUMNS, DataLoader

VALID_ROWS = """customer_id,txn_id,timestamp,amount,direction,counterparty_id,country,channel
C1,T1,2023-01-01T10:00:00,100.50,deposit,X1,US,online
C1,T2,2023-01-02T11:00:00,9500.00,deposit,X2,US,branch
C2,T3,2023-01-03T09:30:00,250.00,withdrawal,X1,GB,atm
"""


def _write_csv(tmp_path: Path, content: str, name: str = "transactions.csv") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _context() -> Context:
    return Context(query="Analyse this dataset for suspicious activity")


def _run(path: Path) -> tuple[Context, object, object]:
    loader = DataLoader()
    return loader.run(_context(), {"path": path})


class TestSuccessfulLoad:
    def test_loads_valid_csv(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS)
        context, result, trace = _run(path)

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.tool == ToolName.DATA_LOADER
        assert trace.rows_in == 3
        assert trace.rows_out == 3
        assert context.raw_df is not None
        assert len(context.raw_df) == 3
        assert result.message is None

    def test_populates_working_df_as_full_copy(self, tmp_path: Path) -> None:
        """Filter may be skipped by the plan, so working_df must default to a
        full, independent copy of raw_df — not merely an alias."""
        path = _write_csv(tmp_path, VALID_ROWS)
        context, _, _ = _run(path)

        assert context.working_df is not None
        pd.testing.assert_frame_equal(
            context.working_df.reset_index(drop=True),
            context.raw_df.reset_index(drop=True),
        )
        # Mutating working_df must never affect raw_df (independent copy).
        context.working_df.loc[0, "amount"] = -1.0
        assert context.raw_df.loc[0, "amount"] != -1.0

    def test_derives_date_and_hour_columns(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS)
        context, _, _ = _run(path)

        assert "date" in context.raw_df.columns
        assert "hour" in context.raw_df.columns
        assert context.raw_df.loc[0, "hour"] == 10

    def test_populates_schema_map(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS)
        context, _, _ = _run(path)

        assert context.schema_map
        for col in REQUIRED_COLUMNS:
            assert col in context.schema_map

    def test_populates_dataset_max_timestamp(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS)
        context, _, _ = _run(path)

        assert context.dataset_max_timestamp == pd.Timestamp("2023-01-03T09:30:00")

    def test_timestamp_and_amount_dtypes_coerced(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS)
        context, _, _ = _run(path)

        assert pd.api.types.is_datetime64_any_dtype(context.raw_df["timestamp"])
        assert pd.api.types.is_float_dtype(context.raw_df["amount"])


class TestMissingFile:
    def test_missing_file_returns_error_trace(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "does_not_exist.csv"
        context, result, trace = _run(missing_path)

        assert trace.status == ExecutionStatus.ERROR
        assert trace.rows_in == 0
        assert trace.rows_out == 0
        assert context.raw_df is None
        assert "not found" in (result.message or "").lower()

    def test_missing_file_does_not_raise(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "does_not_exist.parquet"
        # Must return gracefully, never raise, per module responsibility.
        _context_out, _result, trace = _run(missing_path)
        assert trace.status == ExecutionStatus.ERROR


class TestMissingColumns:
    def test_missing_required_columns_returns_error_trace(self, tmp_path: Path) -> None:
        bad_csv = "customer_id,amount\nC1,100.0\n"
        path = _write_csv(tmp_path, bad_csv, name="bad_schema.csv")
        context, result, trace = _run(path)

        assert trace.status == ExecutionStatus.ERROR
        assert context.raw_df is None
        assert "missing required columns" in (result.message or "").lower()


class TestUnsupportedFormat:
    def test_unsupported_extension_returns_error_trace(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS, name="transactions.txt")
        _context, result, trace = _run(path)

        assert trace.status == ExecutionStatus.ERROR
        assert "unsupported" in (result.message or "").lower()


class TestMalformedData:
    def test_drops_rows_with_bad_timestamp_or_amount(self, tmp_path: Path) -> None:
        rows = (
            "customer_id,txn_id,timestamp,amount,direction,counterparty_id,country,channel\n"
            "C1,T1,2023-01-01T10:00:00,100.50,deposit,X1,US,online\n"
            "C1,T2,NOT-A-DATE,50.00,deposit,X2,US,online\n"
            "C1,T3,2023-01-02T09:00:00,NOT-A-NUMBER,deposit,X3,US,online\n"
        )
        path = _write_csv(tmp_path, rows, name="malformed.csv")
        context, _result, trace = _run(path)

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_in == 3
        assert trace.rows_out == 1
        assert len(context.raw_df) == 1
        assert context.raw_df.iloc[0]["txn_id"] == "T1"

    def test_all_rows_malformed_yields_empty_dataset_not_error(
        self, tmp_path: Path
    ) -> None:
        """Every row fails coercion -> empty, cleaned dataset is still a
        successful, first-class result (D11) — not a load error."""
        rows = (
            "customer_id,txn_id,timestamp,amount,direction,counterparty_id,country,channel\n"
            "C1,T1,NOT-A-DATE,NOT-A-NUMBER,deposit,X1,US,online\n"
        )
        path = _write_csv(tmp_path, rows, name="all_malformed.csv")
        context, _result, trace = _run(path)

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_out == 0
        assert context.raw_df is not None
        assert context.raw_df.empty
        assert context.dataset_max_timestamp is None
        assert "date" in context.raw_df.columns
        assert "hour" in context.raw_df.columns


class TestDeduplication:
    def test_duplicate_txn_id_is_dropped(self, tmp_path: Path) -> None:
        rows = (
            "customer_id,txn_id,timestamp,amount,direction,counterparty_id,country,channel\n"
            "C1,T1,2023-01-01T10:00:00,100.50,deposit,X1,US,online\n"
            "C1,T1,2023-01-01T10:00:00,100.50,deposit,X1,US,online\n"
            "C2,T2,2023-01-02T09:00:00,200.00,withdrawal,X2,GB,atm\n"
        )
        path = _write_csv(tmp_path, rows, name="dupes.csv")
        context, _result, trace = _run(path)

        assert trace.rows_in == 3
        assert trace.rows_out == 2
        assert sorted(context.raw_df["txn_id"]) == ["T1", "T2"]


class TestDeterminism:
    def test_same_input_yields_same_output_shape(self, tmp_path: Path) -> None:
        path = _write_csv(tmp_path, VALID_ROWS)
        context1, _, trace1 = _run(path)
        context2, _, trace2 = _run(path)

        assert trace1.rows_out == trace2.rows_out
        assert list(context1.raw_df.columns) == list(context2.raw_df.columns)
        assert context1.schema_map == context2.schema_map
        pd.testing.assert_frame_equal(
            context1.raw_df.reset_index(drop=True),
            context2.raw_df.reset_index(drop=True),
        )


class TestParquetSupport:
    def test_loads_valid_parquet(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            {
                "customer_id": ["C1", "C2"],
                "txn_id": ["T1", "T2"],
                "timestamp": pd.to_datetime(
                    ["2023-01-01T10:00:00", "2023-01-02T11:00:00"]
                ),
                "amount": [100.0, 200.0],
                "direction": ["deposit", "withdrawal"],
                "counterparty_id": ["X1", "X2"],
                "country": ["US", "GB"],
                "channel": ["online", "atm"],
            }
        )
        path = tmp_path / "transactions.parquet"
        df.to_parquet(path)

        context, _result, trace = _run(path)

        assert trace.status == ExecutionStatus.SUCCESS
        assert trace.rows_out == 2
        assert context.raw_df is not None
