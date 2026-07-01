from unittest.mock import Mock

from actions.comment_attempt import CommentAttemptAction, CommentAttemptArguments
from actions.request_credential_check import (
    RequestCredentialCheckAction,
    RequestCredentialCheckArguments,
)


def test_comment_attempt_action_uses_service():
    action = object.__new__(CommentAttemptAction)
    action.service = Mock()
    action.service.comment_attempt.return_value = {
        "status": "success",
        "message": "updated",
        "data": {"id": 42},
    }

    result = action.run(CommentAttemptArguments(attempt_id=42, comment="needs triage"))

    assert result == {
        "status": "success",
        "message": "updated",
        "data": {"id": 42},
    }
    action.service.comment_attempt.assert_called_once_with(
        attempt_id=42,
        comment="needs triage",
    )


def test_request_credential_check_action_uses_service():
    action = object.__new__(RequestCredentialCheckAction)
    action.service = Mock()
    action.service.request_credential_check.return_value = {
        "status": "success",
        "message": "queued",
        "data": {"id": 42},
    }

    result = action.run(RequestCredentialCheckArguments(attempt_id=42))

    assert result == {
        "status": "success",
        "message": "queued",
        "data": {"id": 42},
    }
    action.service.request_credential_check.assert_called_once_with(42)


def test_comment_attempt_action_falls_back_to_default_result_shape():
    action = object.__new__(CommentAttemptAction)
    action.service = Mock()
    action.service.comment_attempt.return_value = {}

    result = action.run(CommentAttemptArguments(attempt_id=42, comment="needs triage"))

    assert result == {
        "status": "success",
        "message": "Comment updated successfully",
        "data": {},
    }


def test_request_credential_check_action_falls_back_to_default_result_shape():
    action = object.__new__(RequestCredentialCheckAction)
    action.service = Mock()
    action.service.request_credential_check.return_value = {}

    result = action.run(RequestCredentialCheckArguments(attempt_id=42))

    assert result == {
        "status": "success",
        "message": "Credential check requested successfully",
        "data": {},
    }
