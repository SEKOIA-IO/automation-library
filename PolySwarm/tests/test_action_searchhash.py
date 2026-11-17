from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_searchhash import SearchHash
from tests.helpers import autospec_build_client


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SearchHash:
    return SearchHash(module=module, data_path=data_storage)


def _make_assertion(*, verdict: bool, mask: bool = True) -> MagicMock:
    a = MagicMock()
    a.engine_name = "EngineA"
    a.author_name = "enginea"
    a.verdict = verdict
    a.mask = mask
    return a


def _make_mock_result(
    *,
    benign_count: int = 10,
    malicious_count: int = 5,
    abstained_count: int = 0,
    first_seen: str = "2024-01-15T00:00:00Z",
    permalink: str = "https://polyswarm.network/scan/results/abc123",
    polyscore: float = 0.85,
    sha256: str = "cc" * 32,
    window_closed: bool = True,
    family: str | None = "GenericTrojan",
) -> MagicMock:
    result = MagicMock()
    result.sha256 = sha256
    result.first_seen = first_seen
    result.permalink = permalink
    result.polyscore = polyscore
    result.failed = False
    result.window_closed = window_closed

    malicious = [_make_assertion(verdict=True) for _ in range(malicious_count)]
    benign = [_make_assertion(verdict=False) for _ in range(benign_count)]
    abstained = [_make_assertion(verdict=None) for _ in range(abstained_count)]
    result.assertions = malicious + benign + abstained
    result.malicious_assertions = malicious
    result.benign_assertions = benign + abstained

    metadata = MagicMock()
    metadata.json = {"polyunite": {"malware_family": family}}
    result.metadata = metadata
    return result


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_search_hash_returns_result(mock_build_client: MagicMock, action: SearchHash) -> None:
    mock_result = _make_mock_result()
    mock_build_client.return_value.search.return_value = iter([mock_result])

    response = action.run({"query_hash": "ab" * 32})
    assert response is not None

    mock_build_client.assert_called_once_with(action.module.configuration)
    mock_build_client.return_value.search.assert_called_once_with("ab" * 32)
    assert response["benign_detections"] == 10
    assert response["malicious_detections"] == 5
    assert response["family"] == "GenericTrojan"
    assert response["polyscore"] == 0.85
    assert response["permalink"] == "https://polyswarm.network/scan/results/abc123"
    assert response["first_seen"] == "2024-01-15T00:00:00Z"


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_search_hash_no_family(mock_build_client: MagicMock, action: SearchHash) -> None:
    result = _make_mock_result()
    metadata = MagicMock()
    metadata.json = {"exiftool": {}}
    result.metadata = metadata
    mock_build_client.return_value.search.return_value = iter([result])

    response = action.run({"query_hash": "ab" * 32})
    assert response is not None

    assert response["family"] == ""


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_abstaining_engines_are_not_benign(mock_build_client: MagicMock, action: SearchHash) -> None:
    """The client counts an abstention as benign. A detection rule must not."""
    mock_build_client.return_value.search.return_value = [
        _make_mock_result(malicious_count=12, benign_count=0, abstained_count=1)
    ]

    response = action.run({"query_hash": "aa" * 32})

    assert response["malicious_detections"] == 12
    assert response["benign_detections"] == 0


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_unseen_hash_takes_the_unknown_branch_not_a_traceback(
    mock_build_client: MagicMock, action: SearchHash
) -> None:
    """An unseen hash is an ordinary outcome: the playbook routes it, it does not stop."""
    mock_build_client.return_value.search.side_effect = ps_exceptions.NoResultsException("404")

    response = action.run({"query_hash": "bb" * 32})

    assert response["found"] is False
    assert action.error_message is None
    assert action._outputs == {"unknown": True}


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_a_detected_hash_activates_the_detected_branch(mock_build_client: MagicMock, action: SearchHash) -> None:
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result(malicious_count=5, benign_count=2)])
    api.tag_link_get.return_value = _make_tag_link()

    response = action.run({"query_hash": "dd" * 32})

    assert action._outputs == {"detected": True}
    assert response["malicious_detections"] == 5
    assert response["total_detections"] == 7


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_a_clean_hash_activates_the_not_detected_branch(mock_build_client: MagicMock, action: SearchHash) -> None:
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result(malicious_count=0, benign_count=9)])
    api.tag_link_get.return_value = _make_tag_link()

    action.run({"query_hash": "ee" * 32})

    assert action._outputs == {"not detected": True}


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_the_detection_threshold_moves_the_branch(mock_build_client: MagicMock, action: SearchHash) -> None:
    """One lone engine calling it malicious is a judgement call, so the threshold is the operator's."""
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result(malicious_count=1, benign_count=30)])
    api.tag_link_get.return_value = _make_tag_link()

    action.run({"query_hash": "ff" * 32, "detect_threshold": 3})

    assert action._outputs == {"not detected": True}


def _make_tag_link(*, tags: list[str] | None = None, families: list[str] | None = None) -> MagicMock:
    link = MagicMock()
    link.tags = tags if tags is not None else []
    link.families = families if families is not None else []
    return link


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_attribution_is_reported(mock_build_client: MagicMock, action: SearchHash) -> None:
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result()])
    api.tag_link_get.return_value = _make_tag_link(
        tags=["ransomware", "actor:FIN7", "phishing"],
        families=["Emotet", "GenericTrojan"],
    )

    response = action.run({"query_hash": "cc" * 32})
    assert response is not None

    api.tag_link_get.assert_called_once_with("cc" * 32)
    assert response["tags"] == ["ransomware", "actor:FIN7", "phishing"]
    assert response["threat_actor"] == "FIN7"
    # The family already reported leads, and the tag link adds the rest without
    # repeating it. The single family field keeps its old meaning and value.
    assert response["families"] == ["GenericTrojan", "Emotet"]
    assert response["family"] == "GenericTrojan"


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_attribution_empty_still_returns_the_verdict(mock_build_client: MagicMock, action: SearchHash) -> None:
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result()])
    api.tag_link_get.return_value = _make_tag_link()

    response = action.run({"query_hash": "cc" * 32})
    assert response is not None

    assert response["tags"] == []
    assert response["threat_actor"] == ""
    assert response["families"] == ["GenericTrojan"]
    assert response["malicious_detections"] == 5
    assert action.error_message is None


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_attribution_without_an_actor_tag_leaves_the_actor_empty(
    mock_build_client: MagicMock, action: SearchHash
) -> None:
    """An ordinary tag is not an actor. PolySwarm has no actor field, so nothing is guessed."""
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result()])
    api.tag_link_get.return_value = _make_tag_link(tags=["loader", "downloader"])

    response = action.run({"query_hash": "cc" * 32})

    assert response["tags"] == ["loader", "downloader"]
    assert response["threat_actor"] == ""


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_tag_lookup_failure_does_not_fail_the_action(mock_build_client: MagicMock, action: SearchHash) -> None:
    """Attribution is additive. A tag surface the plan cannot reach is not an error."""
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result()])
    api.tag_link_get.side_effect = ps_exceptions.NotFoundException(MagicMock(), "404")

    response = action.run({"query_hash": "cc" * 32})
    assert response is not None

    assert action.error_message is None
    assert response["tags"] == []
    assert response["threat_actor"] == ""
    assert response["families"] == ["GenericTrojan"]
    assert response["malicious_detections"] == 5
    assert response["benign_detections"] == 10
    assert response["polyscore"] == 0.85


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_tag_lookup_returning_objects_is_normalised(mock_build_client: MagicMock, action: SearchHash) -> None:
    """Older deployments return objects carrying a name rather than bare strings."""
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result(family="")])
    api.tag_link_get.return_value = _make_tag_link(
        tags=[{"name": "stealer"}, {"name": "apt:Lazarus"}],
        families=[{"name": "RedLine"}],
    )

    response = action.run({"query_hash": "cc" * 32})

    assert response["tags"] == ["stealer", "apt:Lazarus"]
    assert response["families"] == ["RedLine"]
    assert response["threat_actor"] == "Lazarus"


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_existing_field_names_are_unchanged(mock_build_client: MagicMock, action: SearchHash) -> None:
    """Customer playbooks read these names. Attribution is additive, never a rename."""
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result()])
    api.tag_link_get.return_value = _make_tag_link()

    response = action.run({"query_hash": "cc" * 32})

    assert set(response) == {
        "found",
        "total_detections",
        "benign_detections",
        "families",
        "family",
        "first_seen",
        "malicious_detections",
        "permalink",
        "polyscore",
        "tags",
        "threat_actor",
    }


# --- input validation ---


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_malformed_hash_is_rejected_without_an_api_call(mock_build_client: MagicMock, action: SearchHash) -> None:
    response = action.run({"query_hash": "not-a-hash"})

    assert response is None
    mock_build_client.assert_not_called()
    assert "not a plausible" in action.error_message.lower()


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_wrong_length_hex_is_rejected_without_an_api_call(mock_build_client: MagicMock, action: SearchHash) -> None:
    """33 hex characters is not a valid MD5, SHA1 or SHA256 length."""
    response = action.run({"query_hash": "a" * 33})

    assert response is None
    mock_build_client.assert_not_called()


@pytest.mark.parametrize("query_hash", ["a" * 32, "a" * 40, "a" * 64])
def test_valid_length_hashes_are_accepted(query_hash: str, action: SearchHash) -> None:
    with patch(
        "polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client
    ) as mock_build_client:
        mock_build_client.return_value.search.return_value = iter([_make_mock_result()])
        mock_build_client.return_value.tag_link_get.return_value = _make_tag_link()

        response = action.run({"query_hash": query_hash})

    assert response is not None
    assert response["found"] is True


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_open_assertion_window_takes_the_unknown_branch(mock_build_client: MagicMock, action: SearchHash) -> None:
    """Engines still answering means zero counts, which must never read as clean."""
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result(malicious_count=0, benign_count=0, window_closed=False)])

    response = action.run({"query_hash": "ab" * 32})

    assert response["found"] is False
    assert action._outputs == {"unknown": True}
    assert action.error_message is None
    api.tag_link_get.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_failed_scan_takes_the_unknown_branch(mock_build_client: MagicMock, action: SearchHash) -> None:
    result = _make_mock_result()
    result.failed = True
    mock_build_client.return_value.search.return_value = iter([result])

    action.run({"query_hash": "ab" * 32})

    assert action._outputs == {"unknown": True}


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_null_malware_family_is_an_empty_string(mock_build_client: MagicMock, action: SearchHash) -> None:
    """polyunite can carry a null family, which must not fail the response model."""
    api = mock_build_client.return_value
    result = _make_mock_result()
    result.metadata.json = {"polyunite": {"malware_family": None}}
    api.search.return_value = iter([result])
    api.tag_link_get.return_value = _make_tag_link()

    response = action.run({"query_hash": "ab" * 32})

    assert response["family"] == ""
    assert response["families"] == []
    assert action.error_message is None


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_absent_first_seen_is_empty_and_dates_are_iso(mock_build_client: MagicMock, action: SearchHash) -> None:
    from datetime import UTC, datetime

    api = mock_build_client.return_value
    api.tag_link_get.return_value = _make_tag_link()
    api.search.return_value = iter([_make_mock_result(first_seen=None)])
    assert action.run({"query_hash": "ab" * 32})["first_seen"] == ""

    api.search.return_value = iter([_make_mock_result(first_seen=datetime(2024, 1, 15, 8, 30))])
    assert action.run({"query_hash": "ab" * 32})["first_seen"] == datetime(2024, 1, 15, 8, 30, tzinfo=UTC).isoformat()


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_only_the_first_result_is_consumed(mock_build_client: MagicMock, action: SearchHash) -> None:
    """The client pages lazily, so reading past the first result costs requests for nothing."""
    api = mock_build_client.return_value
    api.tag_link_get.return_value = _make_tag_link()
    consumed: list[int] = []

    def _pages():
        for i in range(3):
            consumed.append(i)
            yield _make_mock_result()

    api.search.return_value = _pages()
    action.run({"query_hash": "ab" * 32})

    assert consumed == [0]


@patch("polyswarm_modules.action_polyswarm_searchhash.build_client", new_callable=autospec_build_client)
def test_a_bare_string_tag_link_is_no_attribution(mock_build_client: MagicMock, action: SearchHash) -> None:
    # Pins a deliberate difference from coerce.as_names, which would read a
    # bare string as one name: here it is treated as no attribution at all.
    api = mock_build_client.return_value
    api.search.return_value = iter([_make_mock_result()])
    api.tag_link_get.return_value = _make_tag_link(tags="actor:FIN7", families="Emotet")

    response = action.run({"query_hash": "cc" * 32})
    assert response is not None

    assert response["tags"] == []
    assert response["threat_actor"] == ""
    assert response["families"] == ["GenericTrojan"]
