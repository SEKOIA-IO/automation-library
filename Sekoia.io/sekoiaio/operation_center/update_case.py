from posixpath import join as urljoin
from typing import Any

import requests
from sekoia_automation.action import Action
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def _is_retryable_request_exception(exc: BaseException) -> bool:
    if isinstance(exc, (requests.ReadTimeout, requests.ConnectionError)):
        return True

    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500

    return False


class UpdateCase(Action):
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

    def case_url(self, case_uuid: str) -> str:
        return urljoin(self.module.configuration["base_url"], f"api/v1/sic/cases/{case_uuid}")

    @property
    def headers(self) -> dict[str, str]:
        api_key = self.module.configuration["api_key"]
        return {"Authorization": f"Bearer {api_key}"}

    def _build_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {field: arguments[field] for field in self.PATCHABLE_FIELDS if field in arguments}

        # The Cases API rejects empty descriptions on update. Ignore explicit empties
        # so status updates (for example reopening) still succeed.
        if payload.get("description") == "":
            payload.pop("description")
            self.log("Ignoring empty case description update because the API does not accept it")

        return payload

    @staticmethod
    def _without_description(payload: dict[str, Any]) -> dict[str, Any]:
        return {field: value for field, value in payload.items() if field != "description"}

    @retry(
        reraise=True,
        retry=retry_if_exception(_is_retryable_request_exception),
        wait=wait_exponential(max=30),
        stop=stop_after_attempt(3),
    )
    def perform_request(self, case_uuid: str, payload: dict[str, Any]) -> requests.Response:
        result = requests.patch(
            self.case_url(case_uuid),
            headers=self.headers,
            json=payload,
            timeout=(5, 30),
        )

        if result.status_code >= 500:
            self.error(f"Could not update case {case_uuid}, status code: {result.status_code}")
            result.raise_for_status()

        return result

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        case_uuid = arguments["uuid"]
        payload = self._build_payload(arguments)
        skipped_description_after_timeout = False

        if not payload:
            self.log("Nothing to update for case", case_uuid=case_uuid)
            return {}

        try:
            result = self.perform_request(case_uuid=case_uuid, payload=payload)
        except requests.ReadTimeout as exc:
            fallback_payload = self._without_description(payload)
            if "description" in payload and fallback_payload:
                self.log(
                    "Case update timed out with description, retrying once without description",
                    level="warning",
                    case_uuid=case_uuid,
                    description_length=len(payload.get("description", "")),
                )
                result = self.perform_request(case_uuid=case_uuid, payload=fallback_payload)
                skipped_description_after_timeout = True
            else:
                description_length = len(payload.get("description", ""))
                raise RuntimeError(
                    "Timed out while updating case after retries. "
                    "This often happens when the case description is very large and the API takes too long to reply. "
                    f"description_length={description_length}"
                ) from exc

        if skipped_description_after_timeout and result.ok:
            self.log(
                "Case update completed but description was skipped after timeout",
                level="warning",
                case_uuid=case_uuid,
            )

        if not result.ok:
            self.error(
                f"Could not update case {case_uuid}, status code: {result.status_code}, response: {result.text}"
            )
            result.raise_for_status()

        if not result.content:
            return {}

        return result.json()
