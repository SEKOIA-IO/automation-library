import json
import pathlib
from functools import cache


@cache
def user_agent() -> str:
    version: str = "unknown"

    try:
        manifest = json.load(pathlib.Path("manifest.json").open())
        version = manifest["version"]
    except Exception:
        pass

    return f"symphony-module-sekoia.io/{version}"
