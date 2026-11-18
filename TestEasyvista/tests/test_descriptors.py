import json
from collections import defaultdict
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import jsonschema

import main
from easyvista_modules.models import EasyVistaConfiguration

ROOT = Path(__file__).resolve().parents[1]


def inline_schema(model):
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def resolve(item):
        if isinstance(item, dict):
            if "$ref" in item:
                siblings = {key: value for key, value in item.items() if key != "$ref"}
                return resolve({**definitions[item["$ref"].rsplit("/", 1)[-1]], **siblings})
            variants = item.get("anyOf", [])
            non_null = [value for value in variants if value.get("type") != "null"]
            if len(variants) == 2 and len(non_null) == 1:
                item = {key: value for key, value in item.items() if key != "anyOf"}
                item.update(non_null[0])
                if item.get("default", "absent") is None:
                    item.pop("default")
            return {key: resolve(value) for key, value in item.items()}
        if isinstance(item, list):
            return [resolve(value) for value in item]
        return item

    return resolve(schema)


def test_connector_registered():
    module = Mock()
    with patch.object(main, "EasyVistaModule", return_value=module):
        main.main()
    registrations = {call.args[1]: call.args[0] for call in module.register.call_args_list}
    connector = json.loads((ROOT / "connector_easyvista_device_assets.json").read_text())
    UUID(connector["uuid"])
    jsonschema.Draft7Validator.check_schema(connector["arguments"])
    assert registrations == {connector["docker_parameters"]: main.EasyVistaDeviceAssetConnector}
    module.register_account_validator.assert_called_once_with(main.EasyVistaAccountValidator)
    module.run.assert_called_once()


def test_manifest_configuration():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["slug"] == "test-easyvista-service-manager"
    assert manifest["categories"] == ["Collaboration Tools"]
    UUID(manifest["uuid"])
    config = manifest["configuration"]
    jsonschema.Draft7Validator.check_schema(config)
    assert config["required"] == ["base_url", "tenant_id"]
    assert config["secrets"] == ["password", "token"]
    assert set(config["properties"]) == set(EasyVistaConfiguration.model_fields)
    assert config["properties"]["tenant_id"]["minLength"] == 1
    assert config["properties"]["tenant_id"]["pattern"] == "\\S"
    model = inline_schema(EasyVistaConfiguration)["properties"]
    for name, prop in config["properties"].items():
        assert (prop.get("description"), prop["type"]) == (model[name].get("description"), model[name]["type"]), name


def descriptor_properties(schema, prefix=""):
    for name, prop in schema.get("properties", {}).items():
        yield prefix + name, name, prop
        yield from descriptor_properties(prop, prefix + name + ".")
        if isinstance(prop.get("items"), dict):
            yield from descriptor_properties(prop["items"], prefix + name + "[].")


CONTEXTUAL_NAMES = {"comment", "description"}


def test_descriptions_are_present_and_consistent():
    connector = json.loads((ROOT / "connector_easyvista_device_assets.json").read_text())
    schemas = {
        "manifest.json": json.loads((ROOT / "manifest.json").read_text())["configuration"],
        "connector_easyvista_device_assets.json": connector["arguments"],
    }
    heads = defaultdict(set)
    for source, schema in schemas.items():
        for path, name, prop in descriptor_properties(schema):
            description = prop.get("description", "")
            assert description, f"{source}: {path} has no description"
            assert not description.endswith(".") and "`" not in description, f"{source}: {path}: {description}"
            if not source.endswith(" results") and name not in CONTEXTUAL_NAMES:
                heads[name].add(description.split(";")[0])
    assert {name: texts for name, texts in heads.items() if len(texts) > 1} == {}
