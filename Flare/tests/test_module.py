from pathlib import Path


def test_scaffold_files_exist() -> None:
    root_dir = Path(__file__).resolve().parents[1]

    assert (root_dir / "manifest.json").is_file()
    assert (root_dir / "main.py").is_file()
