import requests_mock

from microsoft_outlook_modules.action_send_message import SendMessageAction


def test_send_message(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri("POST", "https://graph.microsoft.com/v1.0/users/1111/sendMail", status_code=202)

        action = configured_action(SendMessageAction)
        result = action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "sender": "john.doe@example.com",
                "from": "john.doe@example.com",
                "recipients": ["jane.doe@example.com"],
            }
        )
        assert result == {
            "status": "sent",
            "action": "send_message",
            "target_message_id": None,
        }


def test_send_message_with_all_optional_fields(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri("POST", "https://graph.microsoft.com/v1.0/users/1111/sendMail", status_code=202)

        action = configured_action(SendMessageAction)
        action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "content_type": "html",
                "sender": "sender@example.com",
                "from": "owner@example.com",
                "recipients": ["to1@example.com", "to2@example.com"],
                "cc": ["cc@example.com"],
                "bcc": ["bcc@example.com"],
                "importance": "High",
                "save_to_sent_items": False,
            }
        )

        request = mock.request_history[1]
        payload = request.json()
        assert payload["saveToSentItems"] is False
        assert payload["message"]["importance"] == "High"
        assert payload["message"]["body"]["contentType"] == "html"
        assert len(payload["message"]["toRecipients"]) == 2
        assert payload["message"]["ccRecipients"][0]["emailAddress"]["address"] == "cc@example.com"
        assert payload["message"]["bccRecipients"][0]["emailAddress"]["address"] == "bcc@example.com"


def test_send_message_returns_empty_dict_when_response_is_not_json(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "POST",
            "https://graph.microsoft.com/v1.0/users/1111/sendMail",
            status_code=202,
            content=b"",
        )

        action = configured_action(SendMessageAction)
        result = action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "sender": "john.doe@example.com",
                "from": "john.doe@example.com",
                "recipients": ["jane.doe@example.com"],
            }
        )
        assert result == {
            "status": "sent",
            "action": "send_message",
            "target_message_id": None,
        }


def test_send_message_includes_target_message_id_when_api_returns_id(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "POST",
            "https://graph.microsoft.com/v1.0/users/1111/sendMail",
            status_code=200,
            json={"id": "AAMk-123", "custom": "value"},
        )

        action = configured_action(SendMessageAction)
        result = action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "sender": "john.doe@example.com",
                "from": "john.doe@example.com",
                "recipients": ["jane.doe@example.com"],
            }
        )
        assert result["status"] == "sent"
        assert result["action"] == "send_message"
        assert result["target_message_id"] == "AAMk-123"
        assert result["custom"] == "value"


def test_send_message_ignores_non_dict_json_response(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "POST",
            "https://graph.microsoft.com/v1.0/users/1111/sendMail",
            status_code=200,
            json=["ok"],
        )

        action = configured_action(SendMessageAction)
        result = action.run(
            arguments={
                "user": "1111",
                "subject": "Subject",
                "content": "Hello there",
                "sender": "john.doe@example.com",
                "from": "john.doe@example.com",
                "recipients": ["jane.doe@example.com"],
            }
        )
        assert result == {
            "status": "sent",
            "action": "send_message",
            "target_message_id": None,
        }


def test_send_message_handles_plain_value_error_from_json(configured_action):
    class FakeResponse:
        ok = True

        @staticmethod
        def json():
            raise ValueError("invalid json")

    action = configured_action(SendMessageAction)
    action.client.post = lambda *args, **kwargs: FakeResponse()  # type: ignore[method-assign]

    result = action.run(
        arguments={
            "user": "1111",
            "subject": "Subject",
            "content": "Hello there",
            "sender": "john.doe@example.com",
            "from": "john.doe@example.com",
            "recipients": ["jane.doe@example.com"],
        }
    )

    assert result == {
        "status": "sent",
        "action": "send_message",
        "target_message_id": None,
    }
