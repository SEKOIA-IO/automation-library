from urllib.parse import unquote as url_decoder

import pytest
import requests_mock

from sekoiaio.intelligence_center.actions import GetContextAction
from sekoiaio.operation_center import GetAlert, ListAlerts
from sekoiaio.intelligence_center.actions import PostBundleAction

@pytest.fixture
def get_context_response():
    return {
        "items": [
            {
                "id": "campaign--a8ff459e-beff-4425-b11a-3534b531fea6",
                "type": "campaign",
                "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
                "created": "2023-07-21T13:08:30.508567Z",
                "modified": "2023-09-25T13:13:33.607785Z",
                "revoked": False,
                "external_references": [
                    {
                        "source_name": "FLINT 2023-034 - DarkGate: a trendy loader for Initial Access Brokers"
                    }
                ],
                "object_marking_refs": [
                    "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"
                ],
                "confidence": 100,
                "lang": "en",
                "spec_version": "2.1",
                "x_inthreat_sources_refs": [
                    "identity--357447d7-9229-4ce1-b7fa-f1b83587048e"
                ],
                "x_ic_is_in_flint": True,
                "x_ic_deprecated": False,
                "name": "Phishing emails distributing DarkGate using a job-related lure and targeting France",
                "aliases": [
                    "Job description PDF file infection targets France",
                    "Phishing emails distributing DarkGate using a job-related lure and targeting France"
                ],
                "first_seen": "2023-06-21T00:00:00.000Z",
                "objective": "Unknown"
            }
        ],
        "has_more": False
    }

@pytest.fixture
def get_context_response_with_url():
    return {
        "items": [
            {
                "id": "campaign--a8ff459e-beff-4425-b11a-3534b531fea6",
                "type": "campaign",
                "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
                "created": "2023-07-21T13:08:30.508567Z",
                "modified": "2023-09-25T13:13:33.607785Z",
                "revoked": False,
                "external_references": [
                    {
                        "source_name": "FLINT 2023-034 - DarkGate: a trendy loader for Initial Access Brokers",
                        "url": "https://app.sekoia.io/intelligence/objects/campaign--a8ff459e-beff-4425-b11a-3534b531fea6"
                    }
                ],
                "object_marking_refs": [
                    "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"
                ],
                "confidence": 100,
                "lang": "en",
                "spec_version": "2.1",
                "x_inthreat_sources_refs": [
                    "identity--357447d7-9229-4ce1-b7fa-f1b83587048e"
                ],
                "x_ic_is_in_flint": True,
                "x_ic_deprecated": False,
                "name": "Phishing emails distributing DarkGate using a job-related lure and targeting France",
                "aliases": [
                    "Job description PDF file infection targets France",
                    "Phishing emails distributing DarkGate using a job-related lure and targeting France"
                ],
                "first_seen": "2023-06-21T00:00:00.000Z",
                "objective": "Unknown"
            }
        ],
        "has_more": False
    }


def test_list_alerts_success(get_context_response, get_context_response_with_url):
    arguments = {"term": "8.8.8.8"}
    action: GetContextAction = GetContextAction()
    action.module.configuration = {"base_url": "http://fake.url/", "api_key": "fake_api_key"}

    expected_response = get_context_response
    

    with requests_mock.Mocker() as mock:
        mock.post("http://fake.url/api/v2/inthreat/objects/search", json=expected_response)

        results= action.run(arguments)

        assert results.get("external_references") == get_context_response_with_url

# @pytest.fixture
# def stix_bundle():
#     return {
#         "type": "bundle",
#         "spec_version": "2.0",
#         "id": "bundle--5ce5818a-9d84-42a7-8072-41b195ca48b7",
#         "objects": [
#             {
#                 "id": "identity--55f6ea5e-2c60-40e5-964f-47a8950d210f",
#                 "type": "identity",
#                 "modified": "2019-05-22T17:06:19.504Z",
#                 "identity_class": "organization",
#                 "created": "2019-05-22T17:06:19.504Z",
#                 "name": "CIRCL_8276",
#             },
#             {
#                 "id": "report--5a3faeda-9524-4a8c-a329-b4d302de0b81",
#                 "type": "report",
#                 "modified": "2019-05-22T17:06:19.618Z",
#                 "created_by_ref": "identity--55f6ea5e-2c60-40e5-964f-47a8950d210f",
#                 "name": "OSINT -  Repository containting orignal and decompiled files of TRISIS",
#                 "object_marking_refs": ["marking-definition--a40ab324-4319-4736-bfa4-37b064d3ba68"],
#                 "published": "2019-05-21T13:13:46Z",
#                 "created": "2017-12-24T00:00:00.000Z",
#             },
#         ],
#     }

# def test_post_bundle_results(stix_bundle):
#     arguments = {"bundle": stix_bundle}
#     action = PostBundleAction()

#     action.module.configuration = {
#         "base_url": "http://fake.url/",
#         "api_key": "fake_api_key",
#     }

#     with requests_mock.Mocker() as mock:
#         mock.post(
#             "http://fake.url/api/v2/inthreat/bundles",
#             json={"data": {"content_proposal_id": "some_id"}},
#         )

#         assert action.run(arguments) == {"content_proposal_id": "some_id"}

