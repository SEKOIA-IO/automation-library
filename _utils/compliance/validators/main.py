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

        used_docker_params = []

        calls = list(
            search_python_files(
                paths=[main_path],
                expression=""".//Call/func/Attribute[@attr="register"]/value/Name[@id="module"]/../../../..""",
            )
        )

        for call in calls:
            if isinstance(call, FileFinished):
                continue

            ast_node = call.ast_node

            if len(ast_node.args) > 1:
                arg_node = ast_node.args[1]
                arg_node_value = arg_node.value
                used_docker_params.append(arg_node_value)

            elif len(ast_node.keywords) > 0:
                kwarg_node = ast_node.keywords[0]
                kwarg_node_name = kwarg_node.arg
                if kwarg_node_name == "name":
                    kwarg_node_value = kwarg_node.value.value
                    used_docker_params.append(kwarg_node_value)

        if len(used_docker_params) != len(set(used_docker_params)):
            tmp = set()
            duplicated_docker_params = [
                x for x in used_docker_params if x in tmp or tmp.add(x)
            ]

            for item in duplicated_docker_params:
                result.errors.append(
                    CheckError(
                        filepath=main_path,
                        error=f"Docker parameter `{item}` used multiple times in main.py",
                    )
                )

        docker_params_in_jsons = set(result.options.get("docker_parameters").values())
        absent_in_main_py = docker_params_in_jsons - set(used_docker_params)
        absent_in_jsons = set(used_docker_params) - docker_params_in_jsons

        for item in absent_in_main_py:
            result.errors.append(
                CheckError(
                    filepath=main_path,
                    error=f"Docker parameter `{item}` is not registered in main.py",
                )
            )

        for item in absent_in_jsons:
            result.errors.append(
                CheckError(
                    filepath=main_path,
                    error=f"`Docker parameter {item}` is registered in main.py, but absent in any JSON",
                )
            )
