"""The shared verdict path, driven through the PolySwarm client's own parser.

Every other test in this suite builds results from MagicMock or SimpleNamespace,
which answer to any attribute with any type. That hid a real bug: the client
reads an engine's name with .get(), so it can hand back None, while
AssertionResult typed it str and the ValidationError is deliberately re-raised.
Nothing caught it because no mock ever produced a None name.

So these tests start from a response captured from the live v3 API and let
polyswarm_api.resources.ArtifactInstance parse it, the same object the actions
receive at runtime. The fixture is a search for the EICAR test file: a public
test artifact, so it carries no customer data. Its presigned upload URL was
replaced with a placeholder, since a signed storage URL does not belong in a
repository and nothing in the module reads that field.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from polyswarm_api.resources import ArtifactInstance

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_searchhash import SearchHash
from polyswarm_modules.verdict import has_verdict, tally_assertions
from tests.helpers import autospec_build_client

FIXTURE = Path(__file__).parent / "fixtures" / "search_eicar_instance.json"


def _content() -> dict[str, Any]:
    """A fresh copy of the captured response, so a test cannot mutate another's."""
    return json.loads(FIXTURE.read_text())


def _parsed(content: dict[str, Any] | None = None) -> ArtifactInstance:
    """Parse a captured response the way the client does when an action calls it."""
    return ArtifactInstance(content if content is not None else _content())


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> SearchHash:
    return SearchHash(module=module, data_path=data_storage)


def test_fixture_parses_into_the_shape_the_actions_read() -> None:
    """Guard the fixture itself: a captured payload is only useful while it still parses."""
    result = _parsed()

    assert result.sha256 == "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"
    assert result.window_closed is True
    assert result.failed is False
    assert len(result.assertions) == 13
    # The client parses this into a datetime, not the string every mock supplies,
    # which is why the actions put it through as_text before it reaches a response.
    assert result.first_seen.year == 2019


def test_tally_counts_a_real_result() -> None:
    tally = tally_assertions(_parsed())

    # Thirteen engines answered inside the mask and one of them abstained, so
    # the masked total is one higher than the twelve detections the API reports.
    # An abstention is neither malicious nor benign, which is the whole reason
    # the counts are recomputed here instead of read off the payload.
    assert tally.malicious_count == 12
    assert tally.benign_count == 0
    assert tally.total_count == 13
    assert len(tally.assertions) == 13
    assert has_verdict(_parsed()) is True


def test_engine_without_a_name_parses_and_tallies() -> None:
    """An engine that has not filled in its marketplace profile must not break the tally.

    The client sets engine_name from content['engine'].get('name'), so a missing
    name arrives as None rather than as an absent attribute. Before this was
    handled, tally_assertions raised ValidationError here, and in SearchHashes
    that error escaped the per hash loop and failed the whole batch.
    """
    content = _content()
    content["assertions"][0]["engine"].pop("name")
    content["assertions"][0]["author_name"] = None

    result = _parsed(content)
    # Proving the premise rather than assuming it: the client really does yield None.
    assert result.assertions[0].engine_name is None
    assert result.assertions[0].author_name is None

    tally = tally_assertions(result)

    assert tally.assertions[0].engine_name == ""
    assert tally.assertions[0].author_name == ""
    # The nameless engine still voted malicious, so the counts are unchanged.
    assert tally.malicious_count == 12
    assert tally.total_count == 13


def test_searchhash_runs_end_to_end_on_a_parsed_result(action: SearchHash) -> None:
    """The whole action, from a parsed client object to the dict a playbook receives."""
    with patch(
        "polyswarm_modules.action_polyswarm_searchhash.build_client",
        new_callable=autospec_build_client,
    ) as build:
        api = build.return_value
        api.search.return_value = iter([_parsed()])
        api.tag_link_get.side_effect = Exception("no attribution on this plan")

        response = action.run({"query_hash": "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"})

    assert response is not None
    assert response["found"] is True
    assert response["malicious_detections"] == 12
    assert response["total_detections"] == 13
    assert response["family"] == "EICAR"
    # as_text turned the parsed datetime into a string the response model accepts.
    assert response["first_seen"].startswith("2019-05-17T")
    assert response["permalink"].startswith("https://")


def test_searchhash_runs_end_to_end_with_a_nameless_engine(action: SearchHash) -> None:
    content = _content()
    content["assertions"][0]["engine"].pop("name")
    content["assertions"][0]["author_name"] = None

    with patch(
        "polyswarm_modules.action_polyswarm_searchhash.build_client",
        new_callable=autospec_build_client,
    ) as build:
        api = build.return_value
        api.search.return_value = iter([_parsed(content)])
        api.tag_link_get.side_effect = Exception("no attribution on this plan")

        response = action.run({"query_hash": "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"})

    assert response is not None
    assert response["malicious_detections"] == 12
