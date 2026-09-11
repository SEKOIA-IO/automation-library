import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from sekoia_automation.module import ModuleConfigurationError

from nextron_valhalla_sigma_rules_modules import NextronValhallaSigmaRulesModule
from nextron_valhalla_sigma_rules_modules.models import (
    DEMO_API_KEY,
    NextronValhallaSigmaRulesModuleConfiguration as ModuleConfig,
)

MANIFEST = Path(__file__).resolve().parent.parent / "manifest.json"

A_KEY = "s" * 64


def test_valid_configuration_parses():
    cfg = ModuleConfig(sekoia_api_key=A_KEY)
    assert cfg.sekoia_api_key == A_KEY
    # Both optional fields fall back to their documented defaults.
    assert cfg.valhalla_api_key == DEMO_API_KEY
    assert cfg.sekoia_base_url == "https://api.sekoia.io"


def test_sekoia_api_key_is_required():
    """Without it the trigger issues `Authorization: Bearer ` and every
    Rules Catalog call 401s — a full sync reports thousands of per-rule
    failures with only the first one logged."""
    with pytest.raises(ValidationError) as excinfo:
        ModuleConfig()
    assert "sekoia_api_key" in str(excinfo.value)


@pytest.mark.parametrize("value", ["", "   ", "\n", "\t "])
def test_blank_sekoia_api_key_is_rejected(value):
    """The manifest's `required` array is a key-presence check, so a key
    that is present but blank has to be caught here."""
    with pytest.raises(ValidationError, match="sekoia_api_key"):
        ModuleConfig(sekoia_api_key=value)


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_valhalla_api_key_is_rejected(value):
    """Optional, but explicitly blanking it is a misconfiguration rather
    than a request for the demo key."""
    with pytest.raises(ValidationError, match="valhalla_api_key"):
        ModuleConfig(sekoia_api_key=A_KEY, valhalla_api_key=value)


@pytest.mark.parametrize("value", ["", "  "])
def test_blank_sekoia_base_url_is_rejected(value):
    with pytest.raises(ValidationError, match="sekoia_base_url"):
        ModuleConfig(sekoia_api_key=A_KEY, sekoia_base_url=value)


def test_surrounding_whitespace_is_stripped():
    """Keys and URLs get copy-pasted; a trailing newline on the key would
    otherwise land inside the Authorization header."""
    cfg = ModuleConfig(
        sekoia_api_key=f"  {A_KEY}\n",
        valhalla_api_key=f"\t{DEMO_API_KEY} ",
        sekoia_base_url="  https://app.fra2.sekoia.io/api  ",
    )
    assert cfg.sekoia_api_key == A_KEY
    assert cfg.valhalla_api_key == DEMO_API_KEY
    assert cfg.sekoia_base_url == "https://app.fra2.sekoia.io/api"


# ---------------------------------------------------------------------------
# Manifest / model agreement
# ---------------------------------------------------------------------------
# The SDK reads `required` straight out of manifest.json and raises
# ModuleConfigurationError before the trigger starts, independently of the
# model. Drift between the two would silently drop one of the layers.


def test_manifest_marks_sekoia_api_key_required():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["configuration"]["required"] == ["sekoia_api_key"]


@pytest.mark.parametrize(
    "configuration",
    [
        pytest.param(
            {"sekoia_base_url": "https://api.sekoia.io"},
            id="key-omitted-caught-by-manifest-required",
        ),
        pytest.param({"sekoia_api_key": ""}, id="key-blank-caught-by-validator"),
        pytest.param(
            {"sekoia_api_key": "   "}, id="key-whitespace-caught-by-validator"
        ),
    ],
)
def test_module_rejects_unusable_credentials(configuration):
    """End-to-end: the SDK raises ModuleConfigurationError before the
    trigger runs, so Sekoia reports a configuration problem instead of the
    module burning a full sync on 401s. The omitted case is caught by the
    manifest layer, the blank cases by the model validator."""
    module = NextronValhallaSigmaRulesModule()
    with pytest.raises(ModuleConfigurationError):
        module.configuration = configuration


def test_module_accepts_a_valid_configuration():
    module = NextronValhallaSigmaRulesModule()
    module.configuration = {"sekoia_api_key": f"  {A_KEY}\n"}
    assert module.configuration.sekoia_api_key == A_KEY


def test_manifest_and_model_agree_on_which_fields_are_optional():
    manifest = json.loads(MANIFEST.read_text())
    configuration = manifest["configuration"]
    declared = set(configuration["properties"])
    required = set(configuration["required"])

    assert declared == set(ModuleConfig.model_fields)

    for name, field in ModuleConfig.model_fields.items():
        # A field the manifest lists as required must have no model default,
        # and vice versa — otherwise one layer accepts what the other rejects.
        assert field.is_required() == (name in required), name
        if name not in required:
            assert configuration["properties"][name]["default"] == field.default
