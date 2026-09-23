from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_searchmetadata import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_QUERY_LENGTH,
    SearchMetadata,
)

MODULE_PATH = "polyswarm_modules.action_polyswarm_searchmetadata"


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SearchMetadata:
    return SearchMetadata(module=module, data_path=data_storage)


def _make_item(
    *,
    sha256: str = "aa" * 32,
    sha1: str = "bb" * 20,
    md5: str = "cc" * 16,
    malicious: int = 3,
    benign: int = 7,
    total_detections: int = 10,
    polyscore: float = 0.8,
    family: str = "GenericTrojan",
    tags: list[str] | None = None,
    first_seen: str = "2026-01-01T00:00:00Z",
    last_scanned: str = "2026-02-01T00:00:00Z",
    mimetype: str = "application/x-dosexec",
    filenames: list[str] | None = None,
) -> SimpleNamespace:
    document: dict[str, Any] = {
        "artifact": {"sha256": sha256},
        "scan": {
            "latest_scan": {"polyscore": polyscore},
            "detections": {"malicious": malicious, "benign": benign, "total": total_detections},
        },
        "polyunite": {"malware_family": family} if family else {},
        "tags": tags if tags is not None else [],
    }
    return SimpleNamespace(
        json=document,
        sha256=sha256,
        sha1=sha1,
        md5=md5,
        malicious=malicious,
        benign=benign,
        total_detections=total_detections,
        first_seen=first_seen,
        last_scanned=last_scanned,
        mimetype=mimetype,
        filenames=filenames if filenames is not None else [],
    )


# --- input validation, no API call spent ---


def test_empty_query_is_refused_without_an_api_call(action: SearchMetadata) -> None:
    with patch(f"{MODULE_PATH}.build_client") as mock_build_client:
        response = action.run({"query": ""})

    assert response is None
    mock_build_client.assert_not_called()
    assert "empty query" in action.error_message.lower()


def test_whitespace_only_query_is_refused_without_an_api_call(action: SearchMetadata) -> None:
    with patch(f"{MODULE_PATH}.build_client") as mock_build_client:
        response = action.run({"query": "   "})

    assert response is None
    mock_build_client.assert_not_called()


def test_absurdly_long_query_is_refused_without_an_api_call(action: SearchMetadata) -> None:
    with patch(f"{MODULE_PATH}.build_client") as mock_build_client:
        response = action.run({"query": "a" * (MAX_QUERY_LENGTH + 1)})

    assert response is None
    mock_build_client.assert_not_called()
    assert str(MAX_QUERY_LENGTH) in action.error_message


def test_query_at_the_length_ceiling_is_accepted(action: SearchMetadata) -> None:
    with patch(f"{MODULE_PATH}.build_client") as mock_build_client:
        mock_build_client.return_value.search_by_metadata.return_value = iter([])
        response = action.run({"query": "a" * MAX_QUERY_LENGTH})

    assert response is not None
    mock_build_client.assert_called_once()


def test_limit_above_the_hard_ceiling_is_rejected_by_the_argument_model(action: SearchMetadata) -> None:
    with patch(f"{MODULE_PATH}.build_client") as mock_build_client:
        with pytest.raises(Exception):
            action.run({"query": "tags:ransomware", "limit": MAX_LIMIT + 1})
    mock_build_client.assert_not_called()


# --- found / not found / truncated branches ---


@patch(f"{MODULE_PATH}.build_client")
def test_a_matching_query_activates_the_found_branch(mock_build_client: MagicMock, action: SearchMetadata) -> None:
    mock_build_client.return_value.search_by_metadata.return_value = iter([_make_item()])

    response = action.run({"query": "tags:ransomware"})
    assert response is not None

    assert action._outputs == {"found": True}
    assert response["found"] is True
    assert response["truncated"] is False
    assert response["returned_count"] == 1
    result = response["results"][0]
    assert result["sha256"] == "aa" * 32
    assert result["malicious_detections"] == 3
    assert result["benign_detections"] == 7
    assert result["polyscore"] == 0.8
    assert result["family"] == "GenericTrojan"
    assert result["permalink"].endswith("aa" * 32)


@patch(f"{MODULE_PATH}.build_client")
def test_default_limit_and_no_include_exclude_are_passed_through(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    mock_build_client.return_value.search_by_metadata.return_value = iter([])

    action.run({"query": "tags:ransomware"})

    mock_build_client.return_value.search_by_metadata.assert_called_once_with(
        "tags:ransomware", include=None, exclude=None
    )


@patch(f"{MODULE_PATH}.build_client")
def test_include_and_exclude_are_passed_through_when_supplied(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    mock_build_client.return_value.search_by_metadata.return_value = iter([])

    action.run({"query": "tags:ransomware", "include": ["scan.*"], "exclude": ["strings.*"]})

    mock_build_client.return_value.search_by_metadata.assert_called_once_with(
        "tags:ransomware", include=["scan.*"], exclude=["strings.*"]
    )


@patch(f"{MODULE_PATH}.build_client")
def test_no_matches_activates_the_not_found_branch(mock_build_client: MagicMock, action: SearchMetadata) -> None:
    mock_build_client.return_value.search_by_metadata.return_value = iter([])

    response = action.run({"query": "tags:nonexistent"})
    assert response is not None

    assert action._outputs == {"not found": True}
    assert response["found"] is False
    assert response["results"] == []
    assert response["returned_count"] == 0
    assert response["truncated"] is False


@patch(f"{MODULE_PATH}.build_client")
def test_a_204_style_exception_is_treated_as_not_found_not_an_error(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    mock_build_client.return_value.search_by_metadata.side_effect = ps_exceptions.NoResultsException("204")

    response = action.run({"query": "tags:nonexistent"})

    assert response is not None
    assert response["found"] is False
    assert action.error_message is None
    assert action._outputs == {"not found": True}


@patch(f"{MODULE_PATH}.build_client")
def test_more_matches_than_limit_activates_the_truncated_branch(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    items = [_make_item(sha256=f"{i:02x}" * 32) for i in range(1, 4)]
    mock_build_client.return_value.search_by_metadata.return_value = iter(items)

    response = action.run({"query": "tags:ransomware", "limit": 2})
    assert response is not None

    assert action._outputs == {"truncated": True}
    assert response["found"] is True
    assert response["truncated"] is True
    assert response["returned_count"] == 2
    assert response["limit"] == 2
    assert len(response["results"]) == 2


@patch(f"{MODULE_PATH}.build_client")
def test_exactly_the_limit_worth_of_matches_is_not_truncated(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    items = [_make_item(sha256=f"{i:02x}" * 32) for i in range(1, 3)]
    mock_build_client.return_value.search_by_metadata.return_value = iter(items)

    response = action.run({"query": "tags:ransomware", "limit": 2})
    assert response is not None

    assert action._outputs == {"found": True}
    assert response["truncated"] is False
    assert response["returned_count"] == 2


@pytest.mark.parametrize(
    "limit,item_count,expect_truncated",
    [
        (DEFAULT_LIMIT, DEFAULT_LIMIT, False),
        (DEFAULT_LIMIT, DEFAULT_LIMIT + 1, True),
    ],
)
@patch(f"{MODULE_PATH}.build_client")
def test_truncation_boundary_is_exact(
    mock_build_client: MagicMock, action: SearchMetadata, limit: int, item_count: int, expect_truncated: bool
) -> None:
    items = [_make_item(sha256=f"{i:04x}" * 16) for i in range(item_count)]
    mock_build_client.return_value.search_by_metadata.return_value = iter(items)

    response = action.run({"query": "tags:ransomware", "limit": limit})
    assert response is not None

    assert response["truncated"] is expect_truncated
    assert response["returned_count"] == min(limit, item_count)


# --- exception handling never leaks the client's own message ---


@patch(f"{MODULE_PATH}.build_client")
def test_invalid_query_error_does_not_quote_the_client_exception(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    secret_bearing_message = "GET /search/metadata/query?apikey=SECRET&query=tags:ransomware"
    mock_build_client.return_value.search_by_metadata.side_effect = ps_exceptions.InvalidValueException(
        secret_bearing_message
    )

    response = action.run({"query": "tags:ransomware"})

    assert response is None
    assert "SECRET" not in action.error_message
    assert secret_bearing_message not in action.error_message


@patch(f"{MODULE_PATH}.build_client")
def test_generic_polyswarm_failure_does_not_quote_the_client_exception(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    secret_bearing_message = "request failed with headers Authorization: Bearer SECRET"
    mock_build_client.return_value.search_by_metadata.side_effect = ps_exceptions.PolyswarmAPIException(
        secret_bearing_message
    )

    response = action.run({"query": "tags:ransomware"})

    assert response is None
    assert "SECRET" not in action.error_message
    assert secret_bearing_message not in action.error_message


# --- field shape, missing data fails safe rather than raising ---


@patch(f"{MODULE_PATH}.build_client")
def test_a_document_missing_family_and_tags_still_returns_a_result(
    mock_build_client: MagicMock, action: SearchMetadata
) -> None:
    item = _make_item(family="", tags=[])
    mock_build_client.return_value.search_by_metadata.return_value = iter([item])

    response = action.run({"query": "tags:ransomware"})
    assert response is not None

    result = response["results"][0]
    assert result["family"] == ""
    assert result["tags"] == []
    assert result["families"] == []
