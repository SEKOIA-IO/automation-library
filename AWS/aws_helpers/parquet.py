"""Parquet helpers: they need pandas and pyarrow, so they live apart from the shared aws_helpers.utils."""

from collections.abc import Generator
from typing import BinaryIO

import pandas
import pyarrow
import pyarrow.parquet


def _nullable_integer_columns(parquet: pyarrow.parquet.ParquetFile) -> set[str]:
    """
    Find the top-level integer columns holding at least one null in the whole file.

    The row group statistics are used when present; otherwise only the unresolved columns are scanned,
    batch by batch, without retaining their rows.

    Args:
        parquet: pyarrow.parquet.ParquetFile

    Returns:
        set[str]: The names of the columns
    """
    integer_columns = {field.name for field in parquet.schema_arrow if pyarrow.types.is_integer(field.type)}
    nullable: set[str] = set()
    unknown: set[str] = set()
    for row_group_index in range(parquet.num_row_groups):
        row_group = parquet.metadata.row_group(row_group_index)
        for column_index in range(row_group.num_columns):
            column = row_group.column(column_index)
            if column.path_in_schema not in integer_columns:
                continue
            statistics = column.statistics
            if statistics is None or not statistics.has_null_count:
                unknown.add(column.path_in_schema)
            elif statistics.null_count > 0:
                nullable.add(column.path_in_schema)

    # missing statistics must not silently turn a nullable integer into an integer in the early batches
    unresolved = unknown - nullable
    if unresolved:
        for batch in parquet.iter_batches(batch_size=1000, columns=sorted(unresolved)):
            nullable.update(name for name in unresolved if batch.column(name).null_count > 0)
            if unresolved <= nullable:
                break
    return nullable


def iter_parquet_dataframes(file: BinaryIO, batch_size: int) -> Generator[pandas.DataFrame, None, None]:
    """
    Read a parquet file by batches of rows, as pandas DataFrames typed like the whole file would be.

    Args:
        file: BinaryIO - a seekable file
        batch_size: int - the number of rows per batch

    Yields:
        pandas.DataFrame:
    """
    parquet = pyarrow.parquet.ParquetFile(file)

    # pandas turns an integer column with nulls into float: apply it to every batch, not only those with nulls
    # shortcut: only top-level columns; integers nested in struct/list keep per-batch typing, as per row group before
    float_columns = _nullable_integer_columns(parquet)

    for batch in parquet.iter_batches(batch_size=batch_size):
        df = batch.to_pandas()
        for name in float_columns:
            # a pandas index is part of the parquet schema but not a column of the DataFrame
            if name not in df.columns:
                continue
            dtype = df[name].dtype
            # explicit pandas extension dtypes (e.g. Int64) are kept, as in a whole-file conversion
            if dtype.kind in "iu" and not isinstance(dtype, pandas.api.extensions.ExtensionDtype):
                df[name] = df[name].astype("float64")
        yield df
