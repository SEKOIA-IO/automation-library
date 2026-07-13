from typing import Any

import pytest
import requests_mock
from pydantic import ValidationError

from microsoft_outlook_modules.action_base import MicrosoftGraphActionBase
from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_resolve_message import ResolveMessageAction
from microsoft_outlook_modules.action_search_messages import SearchMessagesAction
from microsoft_outlook_modules.action_send_message import SendMessageAction
from microsoft_outlook_modules.action_update_message import UpdateMessageAction

SEND_ARGUMENTS: dict[str, Any] = {
    "user": "1111",
    "content": "Body",
    "sender": "john.doe@example.com",
    "from": "john.doe@example.com",
    "subject": "Subject",
    "recipients": ["jane.doe@example.com"],
}

ACTIONS_WITH_USER: list[tuple[type[MicrosoftGraphActionBase], dict[str, Any]]] = [
    (GetMessageAction, {"user": "1111", "message_id": "2222"}),
    (DeleteMessageAction, {"user": "1111", "message_id": "2222"}),
    (ForwardMessageAction, {"user": "1111", "message_id": "2222", "recipients": ["john.doe@example.com"]}),
    (UpdateMessageAction, {"user": "1111", "message_id": "2222", "subject": "Changed Subject"}),
    (SendMessageAction, SEND_ARGUMENTS),
    (SearchMessagesAction, {"user": "1111", "email_message_id": "<id@example.com>"}),
    (ResolveMessageAction, {"user": "1111", "email_message_id": "<id@example.com>"}),
]

ACTIONS_WITH_MESSAGE_ID = [
    (action_class, arguments) for action_class, arguments in ACTIONS_WITH_USER if "message_id" in arguments
]


def _without_or_empty(arguments: dict[str, Any], key: str, missing_value: str | None) -> dict[str, Any]:
    if missing_value is None:
        return {k: v for k, v in arguments.items() if k != key}
    return {**arguments, key: missing_value}


@pytest.mark.parametrize("missing_value", [None, ""])
@pytest.mark.parametrize(("action_class", "arguments"), ACTIONS_WITH_USER)
def test_actions_require_user(configured_action, action_class, arguments, missing_value):
    action = configured_action(action_class)

    with requests_mock.Mocker() as mock, pytest.raises(ValidationError):
        action.run(arguments=_without_or_empty(arguments, "user", missing_value))

    assert mock.call_count == 0


@pytest.mark.parametrize("missing_value", [None, ""])
@pytest.mark.parametrize(("action_class", "arguments"), ACTIONS_WITH_MESSAGE_ID)
def test_message_actions_require_message_id(configured_action, action_class, arguments, missing_value):
    action = configured_action(action_class)

    with requests_mock.Mocker() as mock, pytest.raises(ValidationError):
        action.run(arguments=_without_or_empty(arguments, "message_id", missing_value))

    assert mock.call_count == 0
