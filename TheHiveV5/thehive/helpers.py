from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import contextmanager
import shutil


@contextmanager
def copy_to_tempfile(source_path: Path) -> str:
    """Context manager to copy a file to a temporary file."""
    with TemporaryDirectory() as temp_dir:
        temp_file_path = Path(temp_dir) / source_path.name
        with (
            temp_file_path.open("wb") as temp_file,
            source_path.open("rb") as original_file,
        ):
            shutil.copyfileobj(original_file, temp_file)
            temp_file.flush()
        yield str(temp_file_path)
