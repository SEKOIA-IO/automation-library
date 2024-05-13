import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from semver import Version

from .base import Validator
from .models import CheckError, CheckResult


class ManifestValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        manifest_path = module_dir / "manifest.json"

        if not manifest_path.is_file():
            result.errors.append(
                CheckError(filepath=manifest_path, error="manifest.json is missing")
            )
            return

        result.options["manifest_path"] = manifest_path

        try:
            with open(manifest_path, "rt") as f:
                manifest = json.load(f)

        except ValueError:
            result.errors.append(
                CheckError(
                    filepath=manifest_path, error="manifest.json is not readable"
                )
            )
            return

        # @todo check uniqueness among all the modules
        module_uuid = manifest.get("uuid")
        if not module_uuid:
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`uuid` is not present in manifest.json",
                )
            )
        result.options["module_uuid"] = module_uuid

        if "uuid_to_check" not in result.options:
            result.options["uuid_to_check"] = {}
        if "manifest.json" not in result.options["uuid_to_check"]:
            result.options["uuid_to_check"]["manifest.json"] = {}

        result.options["uuid_to_check"]["manifest.json"] = module_uuid

        module_name = manifest.get("name")
        if not module_name:
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`name` is not present in manifest.json",
                )
            )

        module_slug = manifest.get("slug")
        if not module_slug:
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`slug` is not present in manifest.json",
                )
            )

        if not re.match(r"^[a-z]([a-z\_\-]|\d)*$", module_slug):
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`slug` is not correct in manifest.json",
                )
            )
        result.options["module_slug"] = module_slug

        module_version = manifest.get("version")
        if not module_version:
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`version` is not present in manifest.json",
                )
            )

        if Version.is_valid(module_version):
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error=f"'{module_version}' is not valid SemVer version. Read more: https://semver.org/",
                )
            )
        # @todo perhaps, we can fix "2.0" by adding another zero?

        module_configuration = manifest.get("configuration")
        if not module_version:
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`configuration` is not present in manifest.json",
                )
            )

        if not cls.is_valid_json_schema(module_configuration):
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`configuration` is not valid JSON schema",
                )
            )

    @staticmethod
    def is_valid_json_schema(schema: dict) -> bool:
        try:
            Draft7Validator.check_schema(schema)
            return True
        except SchemaError as e:
            return False
