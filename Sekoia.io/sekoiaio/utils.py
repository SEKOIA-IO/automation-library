import json
import pathlib
import sys
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


def should_patch() -> bool:
    return len(sys.argv) >= 2 and sys.argv[1].endswith("_trigger")
