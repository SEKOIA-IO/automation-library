import requests_mock

from microsoft_outlook_modules.action_forward_message import ForwardMessageAction


def test_forward_message(configured_action):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "POST",
            "https://graph.microsoft.com/v1.0/users/1111/messages/2222/forward",
            status_code=202,
            content=b"",
        )

        action = configured_action(ForwardMessageAction)
        result = action.run(arguments={"user": "1111", "message_id": "2222", "recipients": ["john.doe@example.com"]})
        assert result == {
            "status": "forwarded",
            "action": "forward_message",
            "target_message_id": "2222",
        }
