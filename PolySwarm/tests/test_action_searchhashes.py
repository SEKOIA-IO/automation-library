from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_searchhashes import SearchHashes


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SearchHashes:
    return SearchHashes(module=module, data_path=data_storage)


def _make_assertion(*, verdict: bool | None, mask: bool = True, engine_name: str = "EngineA") -> MagicMock:
    a = MagicMock()
    a.engine_name = engine_name
    a.author_name = engine_name.lower()
    a.verdict = verdict
    a.mask = mask
    return a


def _make_result(
    *,
    sha256: str,
    malicious_count: int = 5,
    benign_count: int = 10,
    abstained_count: int = 0,
    polyscore: float = 0.85,
    family: str | None = "GenericTrojan",
) -> MagicMock:
    result = MagicMock()
    result.sha256 = sha256
    result.permalink = f"https://polyswarm.network/scan/results/{sha256}"
    result.polyscore = polyscore
    result.failed = False
    result.window_closed = True

    malicious = [_make_assertion(verdict=True, engine_name=f"Mal{i}") for i in range(malicious_count)]
    benign = [_make_assertion(verdict=False, engine_name=f"Ben{i}") for i in range(benign_count)]
    abstained = [_make_assertion(verdict=None, engine_name=f"Abs{i}") for i in range(abstained_count)]
    result.assertions = malicious + benign + abstained

    metadata = MagicMock()
    metadata.json = {"polyunite": {"malware_family": family}} if family else {"exiftool": {}}
    result.metadata = metadata
    return result


def _search_returning(mapping: dict[str, list[MagicMock]]):
    """Build a search side effect that answers per hash, as the client does."""

    def _search(query_hash: str):
        return iter(mapping.get(query_hash, []))

    return _search


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_returns_one_row_per_hash(mock_build_client: MagicMock, action: SearchHashes) -> None:
    hashes = ["aa" * 32, "bb" * 32, "cc" * 32]
    mock_build_client.return_value.search.side_effect = _search_returning(
        {h: [_make_result(sha256=h)] for h in hashes}
    )

    response = action.run({"hashes": hashes})
    assert response is not None

    mock_build_client.assert_called_once_with(action.module.configuration)
    assert mock_build_client.return_value.search.call_count == 3
    assert [row["hash"] for row in response["results"]] == hashes
    assert [row["sha256"] for row in response["results"]] == hashes
    assert response["not_found"] == []
    assert response["errors"] == []
    assert response["requested_count"] == 3
    assert response["queried_count"] == 3
    assert response["rate_limited"] is False

    first = response["results"][0]
    assert first["malicious_count"] == 5
    assert first["benign_count"] == 10
    assert first["total_count"] == 15
    assert first["polyscore"] == 0.85
    assert first["family"] == "GenericTrojan"
    assert first["permalink"].endswith("aa" * 32)
    # Assertions stay out of the result unless the playbook asks for them.
    assert first["assertions"] == []


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_include_assertions_adds_engine_rows(mock_build_client: MagicMock, action: SearchHashes) -> None:
    query_hash = "aa" * 32
    mock_build_client.return_value.search.side_effect = _search_returning(
        {query_hash: [_make_result(sha256=query_hash, malicious_count=1, benign_count=1)]}
    )

    response = action.run({"hashes": [query_hash], "include_assertions": True})

    assert len(response["results"][0]["assertions"]) == 2
    assert response["results"][0]["assertions"][0]["engine_name"] == "Mal0"


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_unseen_hashes_go_to_not_found(mock_build_client: MagicMock, action: SearchHashes) -> None:
    known = "aa" * 32
    unseen_204 = "bb" * 32
    unseen_404 = "cc" * 32
    empty = "dd" * 32

    def _search(query_hash: str):
        if query_hash == known:
            return iter([_make_result(sha256=known)])
        if query_hash == unseen_204:
            raise ps_exceptions.NoResultsException(MagicMock(), "204")
        if query_hash == unseen_404:
            raise ps_exceptions.NotFoundException(MagicMock(), "404")
        return iter([])

    mock_build_client.return_value.search.side_effect = _search

    response = action.run({"hashes": [known, unseen_204, unseen_404, empty]})

    assert [row["hash"] for row in response["results"]] == [known]
    assert response["not_found"] == [unseen_204, unseen_404, empty]
    assert response["errors"] == []
    assert action.error_message is None


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_per_hash_error_does_not_fail_the_call(mock_build_client: MagicMock, action: SearchHashes) -> None:
    good = "aa" * 32
    bad = "not-a-hash"
    broken = "cc" * 32

    def _search(query_hash: str):
        if query_hash == good:
            return iter([_make_result(sha256=good)])
        raise ps_exceptions.RequestException(MagicMock(), "Error when running the request:\n{...full request...}")

    mock_build_client.return_value.search.side_effect = _search

    response = action.run({"hashes": [good, bad, broken]})

    assert [row["hash"] for row in response["results"]] == [good]
    assert response["errors"] == [
        {
            "hash": bad,
            "reason": "Not a plausible MD5, SHA1 or SHA256 hash: expected 32, 40 or 64 hexadecimal characters",
        },
        {"hash": broken, "reason": "PolySwarm did not return a result for this hash (RequestException)"},
    ]
    # The malformed hash is rejected locally and never spends a request.
    assert mock_build_client.return_value.search.call_count == 2
    assert response["queried_count"] == 2


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_incomplete_and_failed_scans_are_reported_not_scored(
    mock_build_client: MagicMock, action: SearchHashes
) -> None:
    open_window = _make_result(sha256="aa" * 32)
    open_window.window_closed = False
    failed = _make_result(sha256="bb" * 32)
    failed.failed = True
    complete = _make_result(sha256="cc" * 32)

    mock_build_client.return_value.search.side_effect = _search_returning(
        {"aa" * 32: [open_window], "bb" * 32: [failed], "cc" * 32: [complete]}
    )

    response = action.run({"hashes": ["aa" * 32, "bb" * 32, "cc" * 32]})

    assert [row["hash"] for row in response["results"]] == ["cc" * 32]
    reasons = {e["hash"]: e["reason"] for e in response["errors"]}
    assert "assertion window" in reasons["aa" * 32]
    assert "failed" in reasons["bb" * 32]


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_refuses_more_than_one_hundred_hashes(mock_build_client: MagicMock, action: SearchHashes) -> None:
    hashes = [f"{i:064x}" for i in range(101)]

    response = action.run({"hashes": hashes})

    assert response is None
    assert "100" in action.error_message
    assert "101" in action.error_message
    mock_build_client.return_value.search.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_exactly_one_hundred_hashes_is_allowed(mock_build_client: MagicMock, action: SearchHashes) -> None:
    hashes = [f"{i:064x}" for i in range(100)]
    mock_build_client.return_value.search.side_effect = lambda h: iter([_make_result(sha256=h)])

    response = action.run({"hashes": hashes})

    assert response["requested_count"] == 100
    assert mock_build_client.return_value.search.call_count == 100


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_duplicates_are_only_paid_for_once(mock_build_client: MagicMock, action: SearchHashes) -> None:
    """Every lookup costs a request, so a repeated hash must not be billed twice."""
    first = "aa" * 32
    second = "bb" * 32
    mock_build_client.return_value.search.side_effect = lambda h: iter([_make_result(sha256=h)])

    response = action.run({"hashes": [first, second, first, first.upper(), f"  {second}  "]})

    assert mock_build_client.return_value.search.call_count == 2
    assert mock_build_client.return_value.search.call_args_list[0].args == (first,)
    assert mock_build_client.return_value.search.call_args_list[1].args == (second,)
    assert response["requested_count"] == 2
    assert response["queried_count"] == 2
    assert [row["hash"] for row in response["results"]] == [first, second]


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_abstaining_engines_are_not_counted_as_benign(mock_build_client: MagicMock, action: SearchHashes) -> None:
    """The client counts an abstention as benign. A detection rule must not."""
    query_hash = "aa" * 32
    result = _make_result(sha256=query_hash, malicious_count=12, benign_count=0, abstained_count=3)
    result.assertions.append(_make_assertion(verdict=False, mask=False, engine_name="Unmasked"))
    mock_build_client.return_value.search.side_effect = _search_returning({query_hash: [result]})

    response = action.run({"hashes": [query_hash]})

    row = response["results"][0]
    assert row["malicious_count"] == 12
    assert row["benign_count"] == 0
    # The three abstentions count, the assertion outside the bloom mask does not.
    assert row["total_count"] == 15


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_rate_limit_stops_early_and_keeps_what_was_gathered(
    mock_build_client: MagicMock, action: SearchHashes
) -> None:
    hashes = [f"{i:064x}" for i in range(5)]

    def _search(query_hash: str):
        if query_hash == hashes[2]:
            raise ps_exceptions.UsageLimitsExceededException(MagicMock(), "429")
        return iter([_make_result(sha256=query_hash)])

    mock_build_client.return_value.search.side_effect = _search

    response = action.run({"hashes": hashes})

    assert response is not None
    assert mock_build_client.return_value.search.call_count == 3
    assert [row["hash"] for row in response["results"]] == hashes[:2]
    assert response["rate_limited"] is True
    assert response["queried_count"] == 3
    assert "usage limits" in action.error_message
    assert "2 hashes were not looked up" in action.error_message
    # Both rows gathered so far are detections, but the run is incomplete: the
    # partial branch must fire instead of detected, so a playbook cannot read
    # a cut-short run as a clean or complete detected answer.
    assert action._outputs == {"partial": True}


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_fails_only_when_nothing_could_be_looked_up(mock_build_client: MagicMock, action: SearchHashes) -> None:
    mock_build_client.return_value.search.side_effect = ps_exceptions.InvalidValueException("bad hash")

    response = action.run({"hashes": ["nope", "also-nope"]})

    assert response is None
    assert "could be looked up" in action.error_message


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_empty_list_is_refused(mock_build_client: MagicMock, action: SearchHashes) -> None:
    response = action.run({"hashes": ["", "   "]})

    assert response is None
    assert "No hashes" in action.error_message
    mock_build_client.return_value.search.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_missing_family_is_an_empty_string(mock_build_client: MagicMock, action: SearchHashes) -> None:
    query_hash = "aa" * 32
    mock_build_client.return_value.search.side_effect = _search_returning(
        {query_hash: [_make_result(sha256=query_hash, family=None)]}
    )

    response = action.run({"hashes": [query_hash]})

    assert response["results"][0]["family"] == ""


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_api_key_never_reaches_an_error_reason(mock_build_client: MagicMock, action: SearchHashes) -> None:
    """The client can render the whole request, key included, into an exception's text.

    The reason is never built from str(exc): only the exception class name and a
    message written here, so nothing the client puts in its own text, key or
    otherwise, can reach the result.
    """
    good = "aa" * 32
    leaky = "bb" * 32

    def _search(query_hash: str):
        if query_hash == good:
            return iter([_make_result(sha256=good)])
        raise ps_exceptions.RequestException(
            MagicMock(),
            'Error when running the request:\n{\n    "headers": {\n        "Authorization": "test-api-key"\n    }\n}',
        )

    mock_build_client.return_value.search.side_effect = _search

    response = action.run({"hashes": [good, leaky]})

    assert "test-api-key" not in str(response)
    assert response["errors"][0]["reason"] == "PolySwarm did not return a result for this hash (RequestException)"


# --- branch outputs ---


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_at_least_one_detection_activates_the_detected_branch(
    mock_build_client: MagicMock, action: SearchHashes
) -> None:
    clean = "aa" * 32
    hit = "bb" * 32
    mock_build_client.return_value.search.side_effect = _search_returning(
        {
            clean: [_make_result(sha256=clean, malicious_count=0, benign_count=9)],
            hit: [_make_result(sha256=hit, malicious_count=3, benign_count=6)],
        }
    )

    action.run({"hashes": [clean, hit]})

    assert action._outputs == {"detected": True}


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_no_detections_activates_the_not_detected_branch(mock_build_client: MagicMock, action: SearchHashes) -> None:
    clean_one = "aa" * 32
    clean_two = "bb" * 32
    mock_build_client.return_value.search.side_effect = _search_returning(
        {
            clean_one: [_make_result(sha256=clean_one, malicious_count=0, benign_count=9)],
            clean_two: [_make_result(sha256=clean_two, malicious_count=0, benign_count=4)],
        }
    )

    action.run({"hashes": [clean_one, clean_two]})

    assert action._outputs == {"not detected": True}


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_not_found_hashes_alone_activate_the_not_detected_branch(
    mock_build_client: MagicMock, action: SearchHashes
) -> None:
    """Nothing found is a clean answer, not an unknown one: SearchHashes has no unknown branch."""
    unseen = "aa" * 32
    mock_build_client.return_value.search.side_effect = ps_exceptions.NoResultsException(MagicMock(), "204")

    response = action.run({"hashes": [unseen]})

    assert response["not_found"] == [unseen]
    assert action._outputs == {"not detected": True}


# --- input validation ---


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_malformed_hash_is_rejected_without_an_api_call(mock_build_client: MagicMock, action: SearchHashes) -> None:
    response = action.run({"hashes": ["not-a-hash"]})

    assert response is None
    mock_build_client.return_value.search.assert_not_called()
    assert "could be looked up" in action.error_message


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_wrong_length_hex_is_rejected_without_an_api_call(mock_build_client: MagicMock, action: SearchHashes) -> None:
    """33 hex characters is not a valid MD5, SHA1 or SHA256 length."""
    response = action.run({"hashes": ["a" * 33]})

    assert response is None
    mock_build_client.return_value.search.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_searchhashes.build_client")
def test_valid_and_malformed_hashes_mix_without_failing_the_call(
    mock_build_client: MagicMock, action: SearchHashes
) -> None:
    good = "aa" * 32
    malformed = "zz" * 32  # right length, not hex
    mock_build_client.return_value.search.side_effect = _search_returning({good: [_make_result(sha256=good)]})

    response = action.run({"hashes": [good, malformed]})

    assert [row["hash"] for row in response["results"]] == [good]
    assert response["errors"] == [
        {
            "hash": malformed,
            "reason": "Not a plausible MD5, SHA1 or SHA256 hash: expected 32, 40 or 64 hexadecimal characters",
        }
    ]
    assert mock_build_client.return_value.search.call_count == 1
    assert response["queried_count"] == 1
