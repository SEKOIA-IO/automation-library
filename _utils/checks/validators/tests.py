import argparse
import os
from pathlib import Path

from .base import Validator
from .models import CheckError, CheckResult


class TestsValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        tests_path = module_dir / "tests"

        if not tests_path.is_dir():
            result.errors.append(
                CheckError(filepath=tests_path, error="Tests are missing")
            )
            return

        result.options["testa_path"] = tests_path
