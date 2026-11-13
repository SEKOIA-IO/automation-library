import json
from pathlib import Path
from typing import Any

import pytest

from urlscan_modules.formatters import empty_scan_summary

MODULE_DIR = Path(__file__).parent.parent

ACTIONS = {
    "scan_url": "action_scan_url.json",
    "get_scan_result": "action_get_scan_result.json",
    "download_scan_screenshot": "action_download_scan_screenshot.json",
    "search": "action_search.json",
}
SUMMARY_ACTIONS = ["action_scan_url.json", "action_get_scan_result.json"]


def load(name: str) -> dict[str, Any]:
    return json.loads((MODULE_DIR / name).read_text())


def test_docker_parameters_registered_once() -> None:
    main_source = (MODULE_DIR / "main.py").read_text()
    docker_parameters = set()

    for name in ACTIONS.values():
        parameters = load(name)["docker_parameters"]
        docker_parameters.add(parameters)
        assert main_source.count(f'"{parameters}"') == 1

    assert docker_parameters == {
        "urlscan_scan_url",
        "urlscan_get_scan_result",
        "urlscan_download_scan_screenshot",
        "urlscan_search",
    }


@pytest.mark.parametrize("name", SUMMARY_ACTIONS)
def test_scan_results_match_the_summary(name: str) -> None:
    properties = load(name)["results"]["properties"]
    summary = empty_scan_summary()

    assert set(properties) == set(summary)
    for key in ("verdict", "page", "contacted", "stats"):
        assert set(properties[key]["properties"]) == set(summary[key])


def test_required_arguments() -> None:
    assert load(ACTIONS["scan_url"])["arguments"]["required"] == ["url"]
    assert load(ACTIONS["get_scan_result"])["arguments"]["required"] == ["scan_id"]
    assert load(ACTIONS["download_scan_screenshot"])["arguments"]["required"] == ["scan_id"]
    assert "required" not in load(ACTIONS["search"])["arguments"]


def test_slugs() -> None:
    assert {load(name)["slug"] for name in ACTIONS.values()} == set(ACTIONS)
