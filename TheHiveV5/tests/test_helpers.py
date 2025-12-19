from pathlib import Path

from thehive.helpers import copy_to_tempfile


def test_copy_to_tempfile(tmp_path: Path):
    # Create a sample file to copy
    sample_file = tmp_path / "sample.txt"
    sample_content = b"Hello, World!"
    sample_file.write_bytes(sample_content)

    temp_file_path: str
    with copy_to_tempfile(sample_file) as temp_file_path:
        # Verify that the temporary file exists
        temp_path = Path(temp_file_path)
        assert temp_path.exists()
        assert temp_path.name == sample_file.name

        # Verify that the content matches
        with temp_path.open("rb") as temp_file:
            temp_content = temp_file.read()
            assert temp_content == sample_content
