import argparse
import os
from pathlib import Path

from .base import Validator
from .models import CheckError, CheckResult


class DependenciesValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]

        pyproject = module_dir / "pyproject.toml"
        poetry_lock = module_dir / "poetry.lock"

        if not pyproject.is_file():
            result.errors.append(
                CheckError(filepath=pyproject, error="pyproject.toml is missing")
            )

        if not poetry_lock.is_file():
            result.errors.append(
                CheckError(filepath=pyproject, error="poetry.lock is missing")
            )
