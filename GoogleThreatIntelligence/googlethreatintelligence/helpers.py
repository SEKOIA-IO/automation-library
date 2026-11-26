"""Helpers for Google Threat Intelligence module."""

import shutil
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def copy_to_tempfile(source_path: Path) -> Iterator[str]:
    """Context manager to copy a file to a temporary file.

    Ensures the file is materialized on the local filesystem
    (e.g. when data_path points to remote storage such as S3).
    Yields the temporary file path as a string.
    """
    with TemporaryDirectory() as temp_dir:
        temp_file_path = Path(temp_dir) / source_path.name
        with (
            temp_file_path.open("wb") as temp_file,
            source_path.open("rb") as original_file,
        ):
            shutil.copyfileobj(original_file, temp_file)
            temp_file.flush()
            yield str(temp_file_path)
