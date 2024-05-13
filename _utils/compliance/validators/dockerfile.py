import argparse
import os
from pathlib import Path

from .base import Validator
from .models import CheckError, CheckResult


class DockerfileValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        dockerfile_path = module_dir / "Dockerfile"

        if not dockerfile_path.is_file():
            result.errors.append(
                CheckError(filepath=dockerfile_path, error="Dockerfile is missing")
            )
            return

        result.options["dockerfile_path"] = dockerfile_path
