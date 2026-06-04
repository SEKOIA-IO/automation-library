from pathlib import Path
from googlethreatintelligence.helpers import copy_to_tempfile


def test_copy_to_tempfile(tmp_path: Path):
    """Test that copy_to_tempfile copies content and preserves filename."""
    source = tmp_path / "sample.bin"
    source.write_bytes(b"hello world")

    with copy_to_tempfile(source) as temp_path:
        temp = Path(temp_path)
        assert temp.exists()
        assert temp.name == "sample.bin"
        assert temp.read_bytes() == b"hello world"

    # Temp file should be cleaned up after exiting context
    assert not temp.exists()
