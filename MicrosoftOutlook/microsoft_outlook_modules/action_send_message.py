from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .action_base import MicrosoftGraphActionBase


class SendMessageArguments(BaseModel):
    """Represent validated inputs for the send message action."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user: str
    content: str
    content_type: Literal["text", "html"] = "text"
    bcc: list[str] | None = None
    cc: list[str] | None = None
    sender: str
    from_: str = Field(alias="from")
    subject: str
    recipients: list[str]
    importance: Literal["Low", "Normal", "High"] | None = None
    save_to_sent_items: bool = True


class SendMessageAction(MicrosoftGraphActionBase):
    def run(self, arguments: Any) -> Any:
        """Execute the send message action and return normalized results."""

        validated_arguments = SendMessageArguments.model_validate(arguments)
        user_id_or_principal_name = validated_arguments.user
        save_to_sent_items = validated_arguments.save_to_sent_items

        content = validated_arguments.content
        content_type = validated_arguments.content_type
        bcc = validated_arguments.bcc
        cc = validated_arguments.cc
        sender = validated_arguments.sender
        mailbox_owner = validated_arguments.from_
        subject = validated_arguments.subject
        recipients = validated_arguments.recipients
        importance = validated_arguments.importance

        self.log(
            message=(
                "Start send message action "
                f"user={user_id_or_principal_name!r} "
                f"recipient_count={len(recipients)!r} "
                f"cc_count={len(cc or [])!r} "
                f"bcc_count={len(bcc or [])!r} "
                f"save_to_sent_items={save_to_sent_items!r}"
            ),
            level="debug",
        )

        message: dict[str, Any] = {
            "body": {"content": content, "contentType": content_type},
            "toRecipients": [self._generate_recipient(r) for r in recipients],
            "sender": self._generate_recipient(sender),
            "from": self._generate_recipient(mailbox_owner),
            "subject": subject,
        }
        if cc:
            message["ccRecipients"] = [self._generate_recipient(c) for c in cc]
        if bcc:
            message["bccRecipients"] = [self._generate_recipient(b) for b in bcc]
        if importance:
            message["importance"] = importance

        payload: dict[str, Any] = {"message": message, "saveToSentItems": save_to_sent_items}

        response = self.client.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id_or_principal_name}/sendMail",
            json=payload,
            timeout=60,
        )
        self.handle_response(response)

        response_data: dict[str, Any] = {}
        try:
            parsed_body = response.json()
            if isinstance(parsed_body, dict):
                response_data = parsed_body

        except ValueError:
            response_data = {}

        target_message_id = response_data.get("id") if isinstance(response_data.get("id"), str) else None
        self.log(
            message=(
                "Completed send message action "
                f"user={user_id_or_principal_name!r} "
                f"recipient_count={len(recipients)!r} "
                f"target_message_id={target_message_id!r}"
            ),
            level="debug",
        )
        return {
            **response_data,
            "status": "sent",
            "action": "send_message",
            "bcc": bcc,
            "cc": cc,
            "content_type": content_type,
            "from": mailbox_owner,
            "importance": importance,
            "save_to_sent_items": save_to_sent_items,
            "sender": sender,
            "subject": subject,
            "target_message_id": target_message_id,
            "user": user_id_or_principal_name,
            "recipients": recipients,
        }
