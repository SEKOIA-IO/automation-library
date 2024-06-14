import argparse
from pathlib import Path

from pyastgrep.search import FileFinished, search_python_files

from .base import Validator
from .models import CheckError, CheckResult


class MainPYValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        main_path = module_dir / "main.py"

        if not main_path.is_file():
            result.errors.append(
                CheckError(filepath=main_path, error="main.py is missing")
            )
            return

        used_docker_params = {
            item.ast_node.value
            for item in search_python_files(
                paths=[main_path],
                expression='.//Call/func/Attribute[@attr="register"]/value/Name[@id="module"]/../../../../args/Constant',
            )
            if not isinstance(item, FileFinished)
        }

        docker_params_in_jsons = set(result.options.get("docker_parameters").values())
        absent_in_main_py = docker_params_in_jsons - used_docker_params
        absent_in_jsons = used_docker_params - docker_params_in_jsons

        for item in absent_in_main_py:
            result.errors.append(
                CheckError(
                    filepath=main_path, error=f"Docker parameter `{item}` is not registered in main.py"
                )
            )

        for item in absent_in_jsons:
            result.errors.append(
                CheckError(
                    filepath=main_path,
                    error=f"`Docker parameter {item}` is registered in main.py, but absent in any JSON",
                )
            )
