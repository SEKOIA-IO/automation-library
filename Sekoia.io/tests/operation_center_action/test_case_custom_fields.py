import re

import pytest

from sekoiaio.operation_center.cases import CaseActionError, CaseAPIClient

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"

EXTERNAL_ID_UUID = "7d7ad2a8-9a3e-4fd6-8a43-5d0b3b5a9a20"
SOURCE_UUID = "2f1d3f4e-9b1a-4c55-8f0e-3f6b1a2c9d10"
TOOLS_UUID = "a3b5c7d9-1e2f-4a6b-8c0d-2e4f6a8b0c1d"
SEVERITY_UUID = "c0ffee00-1234-4abc-9def-001122334455"
CONTAINED_UUID = "d1e2f3a4-b5c6-4d7e-8f90-a1b2c3d4e5f6"
SENTINEL_OPTION = "5b0d8f7e-4c3a-4b2d-9e1f-0a1b2c3d4e5f"
EDR_OPTION = "6c1e9a8f-5d4b-4c3e-8f2a-1b2c3d4e5f60"
MAIL_OPTION = "7d2fab90-6e5c-4d4f-9a3b-2c3d4e5f6071"

CUSTOM_FIELDS = [
    {"uuid": EXTERNAL_ID_UUID, "name": "External ID", "type": "text", "options": []},
    {
        "uuid": SOURCE_UUID,
        "name": "Source",
        "type": "single_select",
        "options": [{"uuid": SENTINEL_OPTION, "value": "Sentinel"}, {"uuid": EDR_OPTION, "value": "EDR"}],
    },
    {
        "uuid": TOOLS_UUID,
        "name": "Tools",
        "type": "multi_select",
        "options": [{"uuid": EDR_OPTION, "value": "EDR"}, {"uuid": MAIL_OPTION, "value": "Mail gateway"}],
    },
    {"uuid": SEVERITY_UUID, "name": "Severity score", "type": "integer", "options": []},
    {"uuid": CONTAINED_UUID, "name": "Contained", "type": "boolean", "options": []},
]


class Client(CaseAPIClient):
    def run(self, arguments):
        return self._resolve_custom_fields(arguments)


@pytest.fixture
def client(requests_mock):
    requests_mock.get(f"{base_url}custom-fields", json={"items": CUSTOM_FIELDS, "total": len(CUSTOM_FIELDS)})
    client = Client()
    client.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    return client


def test_resolve_custom_fields_by_name(client):
    resolved = client.run(
        {
            "external id": "INC0012345",
            "Source": "sentinel",
            "Tools": ["EDR", "mail gateway"],
            "Severity score": "80",
            "Contained": "false",
        }
    )

    assert resolved == [
        {"uuid": EXTERNAL_ID_UUID, "value": "INC0012345"},
        {"uuid": SOURCE_UUID, "value": [SENTINEL_OPTION]},
        {"uuid": TOOLS_UUID, "value": [EDR_OPTION, MAIL_OPTION]},
        {"uuid": SEVERITY_UUID, "value": 80},
        {"uuid": CONTAINED_UUID, "value": False},
    ]


def test_resolve_custom_fields_by_uuid_and_option_uuid(client):
    resolved = client.run({SOURCE_UUID: SENTINEL_OPTION, SEVERITY_UUID: 80, CONTAINED_UUID: True})

    assert resolved == [
        {"uuid": SOURCE_UUID, "value": [SENTINEL_OPTION]},
        {"uuid": SEVERITY_UUID, "value": 80},
        {"uuid": CONTAINED_UUID, "value": True},
    ]


def test_resolve_custom_fields_without_fields_makes_no_call(requests_mock):
    client = Client()
    client.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    assert client.run({}) == []
    assert requests_mock.call_count == 0


@pytest.mark.parametrize(
    "custom_fields,error",
    [
        (
            {"Ticket": "INC1"},
            "Unknown custom field 'Ticket'. Valid names: Contained, External ID, Severity score, Source, Tools",
        ),
        ({"Source": "Splunk"}, "Unknown option 'Splunk' for the custom field 'Source'. Valid options: EDR, Sentinel"),
        ({"Source": ["Sentinel", "EDR"]}, "The custom field 'Source' takes a single option"),
        ({"Severity score": "high"}, "The custom field 'Severity score' expects an integer, not 'high'"),
        ({"Contained": "yes"}, "The custom field 'Contained' expects true or false, not 'yes'"),
    ],
)
def test_resolve_custom_fields_explains_invalid_values(client, custom_fields, error):
    with pytest.raises(CaseActionError, match=f"^{re.escape(error)}$"):
        client.run(custom_fields)


def test_resolve_custom_fields_reads_every_page(requests_mock):
    requests_mock.get(
        f"{base_url}custom-fields",
        [
            {"json": {"items": CUSTOM_FIELDS[:3], "total": len(CUSTOM_FIELDS)}},
            {"json": {"items": CUSTOM_FIELDS[3:], "total": len(CUSTOM_FIELDS)}},
        ],
    )
    client = Client()
    client.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    assert client.run({"Contained": True}) == [{"uuid": CONTAINED_UUID, "value": True}]
    assert [request.qs["offset"] for request in requests_mock.request_history] == [["0"], ["3"]]
