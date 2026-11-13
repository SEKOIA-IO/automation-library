import json
from collections import defaultdict
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import jsonschema

import main
from easyvista_modules import models
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


def test_all_descriptors_registered_and_match_models():
    descriptors = [json.loads(path.read_text()) for path in ROOT.glob("action_*.json")]
    assert len(descriptors) == 17
    module = Mock()
    with patch.object(main, "EasyVistaModule", return_value=module):
        main.main()
    assert len(module.register.call_args_list) == 18
    registrations = {call.args[1]: call.args[0] for call in module.register.call_args_list}
    assert len(registrations) == 18
    connector = json.loads((ROOT / "connector_easyvista_device_assets.json").read_text())
    assert registrations[connector["docker_parameters"]] is main.EasyVistaDeviceAssetConnector
    uuids = set()
    for descriptor in descriptors:
        UUID(descriptor["uuid"])
        uuids.add(descriptor["uuid"])
        jsonschema.Draft7Validator.check_schema(descriptor["arguments"])
        jsonschema.Draft7Validator.check_schema(descriptor["results"])
        action = registrations[descriptor["docker_parameters"]]
        action_filename = "action_" + descriptor["slug"]
        assert action.__module__ == "easyvista_modules.action." + action_filename
        assert (ROOT / "easyvista_modules" / "action" / (action_filename + ".py")).is_file()
        assert (ROOT / "tests" / "action" / ("test_" + action_filename + ".py")).is_file()
        model = getattr(models, action.__name__ + "Arguments")
        assert descriptor["arguments"] == inline_schema(model)
        for key in descriptor["arguments"]["properties"]:
            assert "." not in key and "[" not in key
    assert len(uuids) == 17
    module.register_account_validator.assert_called_once_with(main.EasyVistaAccountValidator)
    module.run.assert_called_once()


def test_manifest_configuration():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert manifest["slug"] == "easyvista-service-manager"
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


# These names describe a different object in each action (ticket, task, closing action...).
CONTEXTUAL_NAMES = {"comment", "description"}


def test_descriptions_are_present_and_consistent():
    schemas = {"manifest.json": json.loads((ROOT / "manifest.json").read_text())["configuration"]}
    for path in ROOT.glob("action_*.json"):
        descriptor = json.loads(path.read_text())
        schemas[path.name] = descriptor["arguments"]
        schemas[path.name + " results"] = descriptor["results"]
    heads = defaultdict(set)
    for source, schema in schemas.items():
        for path, name, prop in descriptor_properties(schema):
            description = prop.get("description", "")
            assert description, f"{source}: {path} has no description"
            assert not description.endswith(".") and "`" not in description, f"{source}: {path}: {description}"
            if not source.endswith(" results") and name not in CONTEXTUAL_NAMES:
                heads[name].add(description.split(";")[0])
    assert {name: texts for name, texts in heads.items() if len(texts) > 1} == {}
