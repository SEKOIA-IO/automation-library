"""A closed, unfailed result that no engine answered must never read as clean.

Covers an artifact type no engine handles, every engine abstaining, and every
assertion falling outside the bloom mask. All three used to reach "not detected"
at zero out of zero.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_scandomain import ScanDomain
from polyswarm_modules.action_polyswarm_scanfile import ScanFile
from polyswarm_modules.action_polyswarm_scanip import ScanIp
from polyswarm_modules.action_polyswarm_scanurl import ScanUrl
from polyswarm_modules.action_polyswarm_searchhash import SearchHash
from polyswarm_modules.action_polyswarm_searchip import SearchIp
from polyswarm_modules.action_polyswarm_searchurl import SearchUrl
from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.verdict import has_verdict
from tests.helpers import autospec_build_client


def _assertion(verdict: bool | None, mask: bool = True) -> SimpleNamespace:
    return SimpleNamespace(engine_name="Engine", author_name="engine", verdict=verdict, mask=mask)


def _result(assertions: list[SimpleNamespace], *, window_closed: bool = True, failed: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        sha256="ab" * 32,
        sha1="cd" * 20,
        md5="ef" * 16,
        extended_type="URL",
        polyscore=None,
        permalink="https://polyswarm.network/scan/results/x",
        last_scanned="2024-02-01T00:00:00Z",
        first_seen="2024-01-01T00:00:00Z",
        window_closed=window_closed,
        failed=failed,
        assertions=assertions,
    )


NO_ANSWER_CASES = {
    "no_assertions": [],
    "abstained": [_assertion(None)],
    "masked_out": [_assertion(True, mask=False), _assertion(False, mask=False)],
}

# name, class, arguments, client method that reads an existing result
SEARCH_ACTIONS = [
    ("searchhash", SearchHash, {"query_hash": "ab" * 32}, "search"),
    ("searchip", SearchIp, {"ip": "8.8.8.8"}, "search_url"),
    ("searchurl", SearchUrl, {"url": "https://example.com/x"}, "search_url"),
]
SCAN_ACTIONS = [
    ("scanurl", ScanUrl, {"url": "https://example.com/x"}),
    ("scanip", ScanIp, {"ip": "8.8.8.8"}),
    ("scandomain", ScanDomain, {"domain": "example.com"}),
    ("scanfile", ScanFile, {"file": "sample.bin"}),
]


@pytest.fixture
def data_file(data_storage: str) -> None:
    (Path(data_storage) / "sample.bin").write_bytes(b"sample bytes")


@pytest.mark.parametrize("case", NO_ANSWER_CASES)
@pytest.mark.parametrize(("name", "cls", "args", "method"), SEARCH_ACTIONS)
def test_search_with_no_answering_engine_is_unknown(
    name: str, cls: type, args: dict[str, Any], method: str, case: str, data_storage: str, module: PolyswarmModule
) -> None:
    action = cls(module=module, data_path=data_storage)
    with patch(f"polyswarm_modules.action_polyswarm_{name}.build_client", new_callable=autospec_build_client) as build:
        getattr(build.return_value, method).return_value = [_result(NO_ANSWER_CASES[case])]
        action.run(args)

    assert action._outputs == {"unknown": True}


@pytest.mark.parametrize("case", NO_ANSWER_CASES)
@pytest.mark.parametrize(("name", "cls", "args"), SCAN_ACTIONS)
def test_scan_with_no_answering_engine_is_unknown_and_keeps_the_body(
    name: str, cls: type, args: dict[str, Any], case: str, data_storage: str, module: PolyswarmModule, data_file: None
) -> None:
    action = cls(module=module, data_path=data_storage)
    with patch(f"polyswarm_modules.action_polyswarm_{name}.build_client", new_callable=autospec_build_client) as build:
        api = build.return_value
        api.search.return_value = []
        api.search_url.return_value = []
        api.submit.return_value = MagicMock()
        api.lookup.return_value = _result(NO_ANSWER_CASES[case])
        response = action.run(args)

    assert action._outputs == {"unknown": True}
    assert response is not None
    assert response["malicious_count"] == 0


@pytest.mark.parametrize(("name", "cls", "args"), SCAN_ACTIONS)
def test_scan_with_real_assertions_is_unchanged(
    name: str, cls: type, args: dict[str, Any], data_storage: str, module: PolyswarmModule, data_file: None
) -> None:
    for verdict, branch in ((True, "detected"), (False, "not detected")):
        action = cls(module=module, data_path=data_storage)
        with patch(
            f"polyswarm_modules.action_polyswarm_{name}.build_client", new_callable=autospec_build_client
        ) as build:
            api = build.return_value
            api.search.return_value = []
            api.search_url.return_value = []
            api.submit.return_value = MagicMock()
            api.lookup.return_value = _result([_assertion(verdict), _assertion(None)])
            action.run(args)
        assert action._outputs == {branch: True}


@pytest.mark.parametrize(("name", "cls", "args", "method"), SEARCH_ACTIONS)
def test_search_with_real_assertions_is_unchanged(
    name: str, cls: type, args: dict[str, Any], method: str, data_storage: str, module: PolyswarmModule
) -> None:
    action = cls(module=module, data_path=data_storage)
    with patch(f"polyswarm_modules.action_polyswarm_{name}.build_client", new_callable=autospec_build_client) as build:
        getattr(build.return_value, method).return_value = [_result([_assertion(True), _assertion(None)])]
        action.run(args)

    assert action._outputs == {"detected": True}


@pytest.mark.parametrize("case", NO_ANSWER_CASES)
def test_is_complete_rejects_a_closed_result_nobody_answered(case: str) -> None:
    result = _result(NO_ANSWER_CASES[case])
    assert has_verdict(result) is False
    assert PolyswarmAction.is_complete(result) is False


def test_is_complete_accepts_a_closed_result_with_an_answer() -> None:
    assert PolyswarmAction.is_complete(_result([_assertion(False)])) is True
    assert PolyswarmAction.is_complete(_result([_assertion(False)], window_closed=False)) is False
    assert PolyswarmAction.is_complete(_result([_assertion(False)], failed=True)) is False


def test_a_file_name_with_a_nul_byte_is_a_readable_error(data_storage: str, module: PolyswarmModule) -> None:
    action = ScanFile(module=module, data_path=data_storage)
    errors: list[str] = []
    action.error = lambda message, *a, **k: errors.append(message)  # type: ignore[method-assign,assignment]

    assert action.resolve_data_file("bad\x00name.bin") is None
    assert errors == ["File path could not be resolved in the run data directory"]
