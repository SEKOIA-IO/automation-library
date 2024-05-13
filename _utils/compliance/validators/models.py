from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel


class CheckError(BaseModel):
    error: str
    filepath: Path
    fix_label: str | None = None
    fix: Callable[[Any], None] | None = None


class CheckResult(BaseModel):
    name: str
    description: str
    warnings: list[str] = []
    errors: list[CheckError] = []
    options: dict[str, Any] = dict()
