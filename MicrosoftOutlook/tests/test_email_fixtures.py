from email import policy
from email.parser import Parser
from pathlib import Path
from urllib.parse import unquote_plus

import pytest
import requests_mock

from microsoft_outlook_modules.action_search_messages import SearchMessagesAction

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mail_samples"


def parse_eml(path: Path):
    return Parser(policy=policy.default).parsestr(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "file_name,expected_subject,expected_message_id,expected_network_message_id",
    [
        (
            "incoming_sample_anonymized.eml",
            "E2E-OUTLOOK-ANON-01",
            "<incoming-sample-0001@example.test>",
            "11111111-2222-3333-4444-555555555555",
        ),
        (
            "forwarded_sample_anonymized.eml",
            "FW: MicrosoftOutlook e2e update",
            "<forwarded-sample-0001@example.test>",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ),
    ],
)
def test_anonymized_eml_headers_are_parseable(
    file_name, expected_subject, expected_message_id, expected_network_message_id
):
    message = parse_eml(FIXTURES_DIR / file_name)

    assert message["Subject"] == expected_subject
    assert message["Message-ID"] == expected_message_id
    assert message["X-MS-Exchange-Organization-Network-Message-Id"] == expected_network_message_id


def test_anonymized_eml_fixtures_do_not_contain_real_domains():
    for path in FIXTURES_DIR.glob("*.eml"):
        content = path.read_text(encoding="utf-8").lower()
        assert "sekoia.io" not in content
        assert "onmicrosoft.com" not in content


def test_anonymized_fixture_headers_map_pertinently_to_search(configured_action):
    message = parse_eml(FIXTURES_DIR / "incoming_sample_anonymized.eml")
    internet_message_id = message["Message-ID"]
    network_message_id = message["X-MS-Exchange-Organization-Network-Message-Id"]

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            [
                {
                    "status_code": 200,
                    "json": {
                        "value": [
                            {
                                "id": "graph-item-id-from-fixture",
                                "internetMessageId": internet_message_id,
                            }
                        ]
                    },
                },
                {
                    "status_code": 200,
                    "json": {
                        "value": [
                            {
                                "id": "graph-item-id-from-fixture",
                                "internetMessageId": "<another-id@example.test>",
                                "singleValueExtendedProperties": [
                                    {
                                        "id": SearchMessagesAction.NETWORK_MESSAGE_ID_EXTENDED_PROPERTY,
                                        "value": network_message_id,
                                    }
                                ],
                            }
                        ]
                    },
                },
            ],
        )

        search_action = configured_action(SearchMessagesAction)
        search_result = search_action.run(
            arguments={
                "user": "1111",
                "email_message_id": internet_message_id,
            }
        )
        assert search_result["messages"][0]["message_id"] == "graph-item-id-from-fixture"

        search_local_result = search_action.run(
            arguments={
                "user": "1111",
                "email_local_id": network_message_id,
            }
        )
        assert search_local_result["message_ids"] == ["graph-item-id-from-fixture"]

        messages_requests = [request for request in mock.request_history if "/users/1111/messages" in request.url]
        assert len(messages_requests) == 2

        search_query = unquote_plus(messages_requests[0].url.split("?", maxsplit=1)[1])
        assert f"internetMessageId eq '{internet_message_id}'" in search_query

        search_local_query = unquote_plus(messages_requests[1].url.split("?", maxsplit=1)[1])
        assert f"ep/value eq '{network_message_id}'" in search_local_query
