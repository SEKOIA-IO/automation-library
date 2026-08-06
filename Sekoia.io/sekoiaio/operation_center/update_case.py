from typing import Any

from sekoia_automation.action import GenericAPIAction


class UpdateCase(GenericAPIAction):
    verb = "patch"
    endpoint = "api/v1/sic/cases/{uuid}"
    query_parameters: list[str] = []
    timeout = 30
    strip_empty_string_fields = ("description",)
    retry_without_fields_on_failure = ("description",)
    skip_request_if_body_empty = True

    PATCHABLE_FIELDS = [
        "title",
        "description",
        "status_uuid",
        "priority",
        "tags",
        "subscribers",
        "verdict_uuid",
        "custom_status_uuid",
        "custom_priority_uuid",
    ]

    def _build_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {field: arguments[field] for field in self.PATCHABLE_FIELDS if field in arguments}

        # The Cases API rejects empty descriptions on update. Ignore explicit empties
        # so status updates (for example reopening) still succeed.
        if payload.get("description") == "":
            payload.pop("description")
            self.log("Ignoring empty case description update because the API does not accept it")

        return payload

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        payload = self._build_payload(arguments)
        return super().run({"uuid": arguments["uuid"], **payload})
