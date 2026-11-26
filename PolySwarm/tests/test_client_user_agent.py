"""Repo rule 10: every PolySwarm API call carries the module's own User-Agent."""

import ast
import json
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from requests import Response

from polyswarm_modules.client import MODULE_VERSION, USER_AGENT, build_client
from polyswarm_modules.models import PolyswarmModuleConfiguration

MODULE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = MODULE_ROOT / "polyswarm_modules"


def _configuration() -> PolyswarmModuleConfiguration:
    return PolyswarmModuleConfiguration(API_Key="test-api-key", community="default")


def test_user_agent_is_the_sekoia_name_and_never_the_library_default() -> None:
    assert USER_AGENT == f"PolySwarm-Sekoia/{MODULE_VERSION} (Sekoia.io)"
    assert not USER_AGENT.lower().startswith(("polyswarm_api", "python-requests"))


def test_module_version_matches_manifest_and_pyproject() -> None:
    manifest = json.loads((MODULE_ROOT / "manifest.json").read_text())
    pyproject = tomllib.loads((MODULE_ROOT / "pyproject.toml").read_text())

    assert MODULE_VERSION == manifest["version"] == pyproject["project"]["version"]


def test_built_client_session_carries_the_user_agent() -> None:
    api = build_client(_configuration())

    assert api.session.headers["User-Agent"] == USER_AGENT


@pytest.mark.parametrize("timeout", [None, 5])
def test_header_is_on_the_wire(timeout: int | None) -> None:
    """Send a real request through the client's session and read the header back."""
    api = build_client(_configuration(), **({} if timeout is None else {"timeout": timeout}))
    sent = []

    def fake_send(self, request, **kwargs):
        sent.append(request)
        response = Response()
        response.status_code = 200
        response._content = b'{"result": {}, "status": "OK"}'
        response.headers["Content-Type"] = "application/json"
        response.request = request
        response.url = request.url
        return response

    with patch("requests.adapters.HTTPAdapter.send", fake_send):
        try:
            api.account_whois()
        except Exception:
            pass

    assert sent, "no request reached the transport"
    assert all(request.headers["User-Agent"] == USER_AGENT for request in sent)


def test_build_client_is_the_only_place_a_client_is_created() -> None:
    """Every action, the trigger and the account check use build_client.

    If any file constructed PolyswarmAPI itself, that call path would send the
    library default User-Agent, so the header test above would not cover it.
    """
    offenders = []
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in {"PolyswarmAPI", "PolyswarmSession", "Session"} and path.name != "client.py":
                    offenders.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Attribute) and node.attr in {"get", "post", "request"}:
                if getattr(node.value, "id", None) in {"requests", "httpx", "urllib3"}:
                    offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == []
