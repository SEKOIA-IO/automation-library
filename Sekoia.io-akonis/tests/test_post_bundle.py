import json
from unittest.mock import patch

import pytest
import requests_mock
from tenacity import wait_none
from sekoiaio.intelligence_center.actions import PostBundleAction


@pytest.fixture
def stix_bundle():
    return {
        "type": "bundle",
        "spec_version": "2.0",
        "id": "bundle--5ce5818a-9d84-42a7-8072-41b195ca48b7",
        "objects": [
            {
                "id": "identity--55f6ea5e-2c60-40e5-964f-47a8950d210f",
                "type": "identity",
                "modified": "2019-05-22T17:06:19.504Z",
                "identity_class": "organization",
                "created": "2019-05-22T17:06:19.504Z",
                "name": "CIRCL_8276",
            },
            {
                "id": "report--5a3faeda-9524-4a8c-a329-b4d302de0b81",
                "type": "report",
                "modified": "2019-05-22T17:06:19.618Z",
                "created_by_ref": "identity--55f6ea5e-2c60-40e5-964f-47a8950d210f",
                "name": "OSINT -  Repository containting orignal and decompiled files of TRISIS",
                "object_marking_refs": ["marking-definition--a40ab324-4319-4736-bfa4-37b064d3ba68"],
                "published": "2019-05-21T13:13:46Z",
                "created": "2017-12-24T00:00:00.000Z",
            },
        ],
    }


def assert_bundle_was_posted(stix_bundle, arguments, symphony_storage):
    action = PostBundleAction(data_path=symphony_storage)

    action.module.configuration = {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/bundles", json={})
        action.run(arguments)

        assert mock.call_count == 1
        assert mock.last_request.json() == {"data": stix_bundle}


def test_post_bundle(stix_bundle, symphony_storage):
    assert_bundle_was_posted(stix_bundle, {"bundle": stix_bundle}, symphony_storage)


def test_post_bundle_file(stix_bundle, symphony_storage):
    with symphony_storage.joinpath("test_bundle.json").open("w") as out:
        out.write(json.dumps(stix_bundle))

    assert_bundle_was_posted(stix_bundle, {"bundle_path": "test_bundle.json"}, symphony_storage)


@patch.object(PostBundleAction, "error")
def test_post_bundle_error(error_mock, stix_bundle):
    action = PostBundleAction()
    action._wait_param = lambda: wait_none()

    action.module.configuration = {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/bundles", status_code=500, text="error X")
        action.run({"bundle": stix_bundle})
        error_mock.assert_called()


def test_post_bundle_auto_merge(stix_bundle):
    arguments = {"bundle": stix_bundle, "auto_merge": True}
    action = PostBundleAction()

    action.module.configuration = {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/bundles?auto_merge=1", json={})
        action.run(arguments)

        assert mock.call_count == 1
        assert mock.last_request.json() == {"data": stix_bundle}


def test_post_bundle_name(stix_bundle):
    arguments = {"bundle": stix_bundle, "name": "Test CP Name"}
    action = PostBundleAction()

    action.module.configuration = {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/bundles?name=Test%20CP%20Name", json={})
        action.run(arguments)

        assert mock.call_count == 1
        assert mock.last_request.json() == {"data": stix_bundle}


def test_post_bundle_results(stix_bundle):
    arguments = {"bundle": stix_bundle}
    action = PostBundleAction()

    action.module.configuration = {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }

    with requests_mock.Mocker() as mock:
        mock.post(
            "http://fake.url/api/v2/inthreat/bundles",
            json={"data": {"content_proposal_id": "some_id"}},
        )

        assert action.run(arguments) == {"content_proposal_id": "some_id"}


def test_post_empty_bundle(stix_bundle):
    stix_bundle["objects"] = []
    arguments = {"bundle": stix_bundle}
    action = PostBundleAction()

    action.module.configuration = {
        "base_url": "http://fake.url/",
        "api_key": "fake_api_key",
    }
    assert action.run(arguments) is None
