import requests_mock

from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_resolve_message import ResolveMessageAction
from microsoft_outlook_modules.action_update_message import UpdateMessageAction


def test_linear_chain_resolve_get_update_forward_uses_enriched_results(configured_action, get_message_1, message_2):
    message_id = "graph-item-id-chain"

    get_payload = dict(get_message_1)
    get_payload["id"] = message_id

    update_payload = dict(message_2)
    update_payload["id"] = message_id

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/v2.0/token",
            json={"access_token": "foo-token", "token_type": "bearer", "expires_in": 1799},
        )
        mock.register_uri(
            "GET",
            "https://graph.microsoft.com/v1.0/users/1111/messages",
            json={"value": [{"id": message_id}]},
        )
        mock.register_uri(
            "GET",
            f"https://graph.microsoft.com/v1.0/users/1111/messages/{message_id}",
            json=get_payload,
        )
        mock.register_uri(
            "PATCH",
            f"https://graph.microsoft.com/v1.0/users/1111/messages/{message_id}",
            status_code=200,
            json=update_payload,
        )
        mock.register_uri(
            "POST",
            f"https://graph.microsoft.com/v1.0/users/1111/messages/{message_id}/forward",
            status_code=202,
            content=b"",
        )

        resolve_action = configured_action(ResolveMessageAction)
        get_action = configured_action(GetMessageAction)
        update_action = configured_action(UpdateMessageAction)
        forward_action = configured_action(ForwardMessageAction)

        resolve_result = resolve_action.run(
            arguments={
                "user": "1111",
                "email_message_id": "<chain-sample-message-id@example.test>",
            }
        )
        assert resolve_result["message_id"] == message_id

        get_result = get_action.run(
            arguments={
                "user": "1111",
                "message_id": resolve_result["message_id"],
            }
        )
        assert get_result["message_id"] == message_id

        update_result = update_action.run(
            arguments={
                "user": "1111",
                "message_id": get_result["message_id"],
                "subject": "Updated subject",
            }
        )
        assert update_result["message_id"] == message_id

        forward_result = forward_action.run(
            arguments={
                "user": "1111",
                "message_id": update_result["message_id"],
                "recipients": ["recipient@example.test"],
            }
        )
        assert forward_result["target_message_id"] == message_id
        assert forward_result["status"] == "forwarded"
        assert forward_result["action"] == "forward_message"
