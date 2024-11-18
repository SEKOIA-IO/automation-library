import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from semver import Version

from .base import Validator
from .models import CheckError, CheckResult

ALLOWED_MANIFEST_CATEGORIES = {
    "Applicative",
    "Cloud Providers",
    "Collaboration Tools",
    "Email",
    "Endpoint",
    "Generic",
    "IAM",
    "Network",
    "Threat Intelligence",
}


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

        elif not re.match(r"^[a-z]([a-z_.\-]|\d)*$", module_slug):
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

        if not Version.is_valid(module_version):
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error=f"'{module_version}' is not valid semantic version. Read more: https://semver.org/",
                )
            )

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

        module_categories = manifest.get("categories", [])
        if len(module_categories) == 0:
            result.errors.append(
                CheckError(
                    filepath=manifest_path,
                    error="`category` is non-existent or doesn't contain any category",
                )
            )

        else:
            for category in module_categories:
                if category not in ALLOWED_MANIFEST_CATEGORIES:
                    result.errors.append(
                        CheckError(
                            filepath=manifest_path,
                            error=f"`category` could not contain value '{category}'",
                        )
                    )

    @staticmethod
    def is_valid_json_schema(schema: dict) -> bool:
        try:
            Draft7Validator.check_schema(schema)
            return True
        except SchemaError as e:
            return False
