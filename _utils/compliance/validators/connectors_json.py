import argparse
import json
import uuid
from functools import partial
from pathlib import Path

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

from .base import Validator
from .models import CheckError, CheckResult

# Keys of an asset connector descriptor (`"type": "asset"`). An unknown key is ignored by the platform,
# e.g. `feature-flag` instead of `feature_flags` silently leaves the connector without its flag.
ASSET_CONNECTOR_REQUIRED_KEYS = {
    "name",
    "description",
    "uuid",
    "docker_parameters",
    "type",
    "capability",
    "arguments",
}
ASSET_CONNECTOR_ALLOWED_KEYS = ASSET_CONNECTOR_REQUIRED_KEYS | {
    "feature_flags",
    "slug",
    "execution_modes",
    "on_premise_action",
}
ASSET_CONNECTOR_CAPABILITIES = {
    "host_detection",
    "account_detection",
    "software_enrichment",
    "vulnerability_enrichment",
}
# Arguments the platform fills for every asset connector: they must be hidden from the user form
ASSET_CONNECTOR_INTERNAL_ARGUMENTS = {
    "sekoia_base_url",
    "sekoia_api_key",
    "frequency",
    "batch_size",
}
ASSET_CONNECTOR_SECRET_ARGUMENTS = {"sekoia_api_key"}


class ConnectorsJSONValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        connector_jsons = module_dir.glob("connector_*.json")

        result.options["connectors"] = {}
        for path in connector_jsons:
            cls.validate_connector_json(path, result, args)

    @classmethod
    def validate_connector_json(
        cls, path: Path, result: CheckResult, args: argparse.Namespace
    ):
        try:
            with open(path, "rt") as file:
                raw = json.load(file)

        except ValueError:
            result.errors.append(CheckError(filepath=path, error=f"can't load JSON"))
            return

        if not isinstance(raw.get("name"), str):
            result.errors.append(
                CheckError(filepath=path, error=f"`name` is not present")
            )

        if not isinstance(raw.get("uuid"), str):
            result.errors.append(
                CheckError(
                    filepath=path,
                    error=f"`uuid` is not present",
                    fix_label="Generate random UUID",
                    fix=partial(cls.set_random_uuid, path=path),
                )
            )
        else:
            if "uuid_to_check" not in result.options:
                result.options["uuid_to_check"] = {}
            if path.name not in result.options["uuid_to_check"]:
                result.options["uuid_to_check"][path.name] = {}
            result.options["uuid_to_check"][path.name] = raw.get("uuid")

        if not isinstance(raw.get("description"), str):
            result.errors.append(
                CheckError(filepath=path, error=f"`description` is not present")
            )

        if not isinstance(raw.get("docker_parameters"), str):
            result.errors.append(
                CheckError(filepath=path, error=f"`docker_parameters` is not present")
            )
        else:
            if "docker_parameters" not in result.options:
                result.options["docker_parameters"] = {}
            if path.name not in result.options["docker_parameters"]:
                result.options["docker_parameters"][path.name] = {}

            result.options["docker_parameters"][path.name] = raw.get(
                "docker_parameters"
            )

        if not isinstance(raw.get("arguments"), dict):
            result.errors.append(
                CheckError(filepath=path, error=f"`arguments` is not present")
            )

        elif not cls.is_valid_json_schema(raw["arguments"]):
            result.errors.append(
                CheckError(filepath=path, error=f"`arguments` is not valid JSON schema")
            )

        if raw.get("type") == "asset":
            cls.validate_asset_connector(raw, path, result)

        # @todo perhaps check if results present? (they shouldn't be)

    @classmethod
    def validate_asset_connector(
        cls, raw: dict, path: Path, result: CheckResult
    ) -> None:
        missing_keys = ASSET_CONNECTOR_REQUIRED_KEYS - raw.keys()
        for key in sorted(missing_keys):
            result.errors.append(
                CheckError(filepath=path, error=f"`{key}` is not present")
            )

        unknown_keys = raw.keys() - ASSET_CONNECTOR_ALLOWED_KEYS
        for key in sorted(unknown_keys):
            result.errors.append(
                CheckError(
                    filepath=path,
                    error=f"unknown key `{key}` (allowed: {', '.join(sorted(ASSET_CONNECTOR_ALLOWED_KEYS))})",
                )
            )

        if (
            "capability" in raw
            and raw["capability"] not in ASSET_CONNECTOR_CAPABILITIES
        ):
            result.errors.append(
                CheckError(
                    filepath=path,
                    error=f"`capability` must be one of {', '.join(sorted(ASSET_CONNECTOR_CAPABILITIES))}",
                )
            )

        feature_flags = raw.get("feature_flags", [])
        if not isinstance(feature_flags, list) or not all(
            isinstance(flag, str) for flag in feature_flags
        ):
            result.errors.append(
                CheckError(
                    filepath=path, error="`feature_flags` must be a list of strings"
                )
            )

        arguments = raw.get("arguments")
        if not isinstance(arguments, dict):
            return

        properties = arguments.get("properties", {})
        for name in sorted(ASSET_CONNECTOR_INTERNAL_ARGUMENTS - properties.keys()):
            result.errors.append(
                CheckError(
                    filepath=path, error=f"`arguments.properties.{name}` is not present"
                )
            )

        internal = set(arguments.get("internal", []))
        for name in sorted(ASSET_CONNECTOR_INTERNAL_ARGUMENTS - internal):
            result.errors.append(
                CheckError(
                    filepath=path,
                    error=f"`{name}` is missing from `arguments.internal`",
                )
            )

        secrets = set(arguments.get("secrets", []))
        for name in sorted(ASSET_CONNECTOR_SECRET_ARGUMENTS - secrets):
            result.errors.append(
                CheckError(
                    filepath=path, error=f"`{name}` is missing from `arguments.secrets`"
                )
            )

    @staticmethod
    def is_valid_json_schema(schema: dict) -> bool:
        try:
            Draft7Validator.check_schema(schema)
            return True
        except SchemaError as e:
            return False

    @staticmethod
    def set_random_uuid(path: Path):
        with open(path, "rt") as file:
            manifest = json.load(file)

        manifest["uuid"] = str(uuid.uuid4())

        with open(path, "wt") as file:
            json.dump(manifest, file, indent=2)
