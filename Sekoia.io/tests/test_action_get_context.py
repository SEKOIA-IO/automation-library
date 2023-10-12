# import pytest
# import requests_mock

# from sekoiaio.intelligence_center.actions import GetContextAction


# @pytest.fixture
# def get_context_response():
#     return {
#         "items": [
#             {
#                 "id": "campaign--a8ff459e-beff-4425-b11a-3534b531fea6",
#                 "type": "campaign",
#                 "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
#                 "created": "2023-07-21T13:08:30.508567Z",
#                 "modified": "2023-09-25T13:13:33.607785Z",
#                 "revoked": False,
#                 "external_references": [
#                     {
#                         "source_name": "FLINT 2023-034 - DarkGate: a trendy loader for Initial Access Brokers"
#                     }
#                 ],
#                 "object_marking_refs": [
#                     "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"
#                 ],
#                 "confidence": 100,
#                 "lang": "en",
#                 "spec_version": "2.1",
#                 "x_inthreat_sources_refs": [
#                     "identity--357447d7-9229-4ce1-b7fa-f1b83587048e"
#                 ],
#                 "x_ic_is_in_flint": True,
#                 "x_ic_deprecated": False,
#                 "name": "Phishing emails distributing DarkGate using a job-related lure and targeting France",
#                 "aliases": [
#                     "Job description PDF file infection targets France",
#                     "Phishing emails distributing DarkGate using a job-related lure and targeting France"
#                 ],
#                 "first_seen": "2023-06-21T00:00:00.000Z",
#                 "objective": "Unknown"
#             }
#         ],
#         "has_more": False
#     }

# @pytest.fixture
# def get_context_response_with_url():
#     return {
#         "items": [
#             {
#                 "id": "campaign--a8ff459e-beff-4425-b11a-3534b531fea6",
#                 "type": "campaign",
#                 "created_by_ref": "identity--357447d7-9229-4ce1-b7fa-f1b83587048e",
#                 "created": "2023-07-21T13:08:30.508567Z",
#                 "modified": "2023-09-25T13:13:33.607785Z",
#                 "revoked": False,
#                 "external_references": [
#                     {
#                         "source_name": "FLINT 2023-034 - DarkGate: a trendy loader for Initial Access Brokers",
#                         "url": "https://app.sekoia.io/intelligence/objects/campaign--a8ff459e-beff-4425-b11a-3534b531fea6"
#                     }
#                 ],
#                 "object_marking_refs": [
#                     "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"
#                 ],
#                 "confidence": 100,
#                 "lang": "en",
#                 "spec_version": "2.1",
#                 "x_inthreat_sources_refs": [
#                     "identity--357447d7-9229-4ce1-b7fa-f1b83587048e"
#                 ],
#                 "x_ic_is_in_flint": True,
#                 "x_ic_deprecated": False,
#                 "name": "Phishing emails distributing DarkGate using a job-related lure and targeting France",
#                 "aliases": [
#                     "Job description PDF file infection targets France",
#                     "Phishing emails distributing DarkGate using a job-related lure and targeting France"
#                 ],
#                 "first_seen": "2023-06-21T00:00:00.000Z",
#                 "objective": "Unknown"
#             }
#         ],
#         "has_more": False
#     }


# def assert_get_context_without_url(get_context_response, get_context_response_with_url, arguments, symphony_storage):
#     action = GetContextAction(data_path=symphony_storage)

#     action.module.configuration = {
#         "base_url": "http://fake.url/",
#         "api_key": "fake_api_key",
#     }

#     with requests_mock.Mocker() as mock:
#         mock.post("http://fake.url/api/v2/inthreat/objects/search?limit=10", json=get_context_response)
#         action.run(arguments)

#         assert action.run(arguments) == get_context_response_with_url


# def assert_get_context_without_url(get_context_response, arguments, symphony_storage):
#     action = GetContextAction(data_path=symphony_storage)

#     action.module.configuration = {
#         "base_url": "http://fake.url/",
#         "api_key": "fake_api_key",
#     }

#     with requests_mock.Mocker() as mock:
#         mock.post("http://fake.url/api/v2/inthreat/objects/search?limit=10", json=get_context_response)
#         action.run(arguments)

#         assert action.run(arguments) == get_context_response