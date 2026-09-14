from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .action_base import MicrosoftGraphActionBase


class UpdateMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user: str
    message_id: str
    content: str | None = None
    bcc: list[str] | None = None
    cc: list[str] | None = None
    sender: str | None = None
    from_: str | None = Field(default=None, alias="from")
    subject: str | None = None
    recipients: list[str] | None = None
    importance: Literal["Low", "Normal", "High"] | None = None

    @model_validator(mode="after")
    def validate_at_least_one_update_field(self) -> "UpdateMessageArguments":
        if all(
            value is None
            for value in (
                self.content,
                self.bcc,
                self.cc,
                self.sender,
                self.from_,
                self.subject,
                self.recipients,
                self.importance,
            )
        ):
            raise ValueError("At least one updatable field must be provided")
        return self


class UpdateMessageAction(MicrosoftGraphActionBase):
    @staticmethod
    def fill_non_empty(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    @staticmethod
    def generate_recipient(email: str) -> dict[str, Any]:
        return {"emailAddress": {"name": email, "address": email}}

    def run(self, arguments: Any) -> Any:
        validated_arguments = UpdateMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        message_id = validated_arguments.message_id

        content = validated_arguments.content
        bcc = validated_arguments.bcc
        cc = validated_arguments.cc
        sender = validated_arguments.sender
        mailbox_owner = validated_arguments.from_
        subject = validated_arguments.subject
        recipients = validated_arguments.recipients
        importance = validated_arguments.importance

        payload: dict[str, Any] = self.fill_non_empty(
            {
                "body": {"content": content, "contentType": "text"} if content is not None else None,
                "bccRecipients": [self.generate_recipient(item) for item in bcc] if bcc is not None else None,
                "ccRecipients": [self.generate_recipient(item) for item in cc] if cc is not None else None,
                "sender": self.generate_recipient(sender) if sender is not None else None,
                "from": self.generate_recipient(mailbox_owner) if mailbox_owner is not None else None,
                "subject": subject,
                "toRecipients": (
                    [self.generate_recipient(item) for item in recipients] if recipients is not None else None
                ),
                "importance": importance,
            }
        )

        response = self.client.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/messages/{message_id}",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        result: dict[str, Any] = {}
        try:
            parsed_body = response.json()
            if isinstance(parsed_body, dict):
                result = parsed_body
        except requests.exceptions.JSONDecodeError:
            result = {}

        resolved_message_id = result.get("id") if isinstance(result.get("id"), str) else message_id
        normalized_result = self._snake_case_keys(result)
        normalized_result.pop("id", None)
        normalized_result["message_id"] = resolved_message_id
        return normalized_result
