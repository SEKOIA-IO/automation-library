import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_scanurl import ScanUrl
from polyswarm_modules.action_polyswarm_searchhashes import SearchHashes
from polyswarm_modules.base import ARGUMENTS_MODEL_SUFFIX, PolyswarmAction


@pytest.fixture
def scanurl(data_storage: str, module: PolyswarmModule) -> ScanUrl:
    return ScanUrl(module=module, data_path=data_storage)


@pytest.fixture
def searchhashes(data_storage: str, module: PolyswarmModule) -> SearchHashes:
    return SearchHashes(module=module, data_path=data_storage)


@patch("polyswarm_modules.action_polyswarm_scanurl.build_client")
def test_out_of_range_number_is_an_action_error(mock_build_client: MagicMock, scanurl: ScanUrl) -> None:
    result = scanurl.run({"url": "https://example.com/x", "max_wait_seconds": 10**9})

    assert result is None
    assert scanurl.error_message is not None
    assert "max_wait_seconds" in scanurl.error_message
    assert "Traceback" not in scanurl.error_message
    mock_build_client.assert_not_called()


def test_wrong_typed_argument_is_an_action_error(searchhashes: SearchHashes) -> None:
    result = searchhashes.run({"hashes": "a" * 64})

    assert result is None
    assert searchhashes.error_message is not None
    assert "hashes" in searchhashes.error_message
    assert "list" in searchhashes.error_message
    assert "Traceback" not in searchhashes.error_message


def test_missing_required_argument_names_the_field(scanurl: ScanUrl) -> None:
    result = scanurl.run({})

    assert result is None
    assert scanurl.error_message is not None
    assert "'url' is required" in scanurl.error_message


def test_rejected_value_is_not_echoed(scanurl: ScanUrl) -> None:
    scanurl.run({"url": "https://example.com/secret-token-123", "max_wait_seconds": "soon"})

    assert scanurl.error_message is not None
    assert "secret-token-123" not in scanurl.error_message


def test_execute_reports_the_error_without_a_traceback(scanurl: ScanUrl) -> None:
    scanurl._results = scanurl.run({"url": "https://example.com/x", "max_wait_seconds": -5})

    assert scanurl.error_message is not None
    assert "max_wait_seconds" in scanurl.error_message


def test_a_payload_validation_error_is_not_reported_as_a_bad_argument(
    data_storage: str, module: PolyswarmModule
) -> None:
    """A response model refusing a payload must not read as a playbook input error."""

    class Payload(BaseModel):
        failed: bool

    class PayloadAction(PolyswarmAction):
        def run(self, arguments: dict[str, object]) -> None:
            Payload(failed=None)  # type: ignore[arg-type]

    action = PayloadAction(module=module, data_path=data_storage)
    with pytest.raises(ValidationError):
        action.run({})


def test_every_action_names_its_argument_model_with_the_expected_suffix() -> None:
    """The guard tells argument models from payload models by name, so the names matter."""
    module_root = Path(__file__).resolve().parent.parent / "polyswarm_modules"
    for path in sorted(module_root.glob("action_polyswarm_*.py")):
        source = path.read_text()
        names = re.findall(r"^class (\w+)\(BaseModel\):", source, re.MULTILINE)
        for built in re.findall(r"(\w+)\(\*\*arguments\)", source):
            assert built.endswith(ARGUMENTS_MODEL_SUFFIX), f"{path.name} builds {built} from arguments"
            assert built in names, f"{path.name} builds {built} which is not a model in this file"
