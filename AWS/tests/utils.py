from pathlib import Path

import orjson


def read_file(storage: Path, directory: str, filename: str) -> list[str]:
    filepath = storage.joinpath(directory).joinpath(filename)
    with filepath.open("rb") as f:
        return orjson.loads(f.read())
