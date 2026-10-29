"""Case actions that prepare their request before forwarding it to the Cases API.

`Create case` and `Edit case` still send their arguments as they come, like any generic API action, and only add:

- names accepted for the custom status, the custom priority and the verdict, resolved to their UUIDs
- `assignees` on `Create case`, turned into subscribers of type `assignee`
- `template_uuid` on `Create case`, applied once the case exists
"""

from typing import Any, ClassVar
from urllib.parse import urljoin
from uuid import UUID

import requests
from sekoia_automation.action import GenericAPIAction
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from sekoiaio.operation_center.constants import base_url

ASSIGNEE = "assignee"


class CaseActionError(Exception):
    """Raised when a case action cannot prepare its request. The message is shown to the playbook user."""


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return isinstance(exc, requests.RequestException)


def _is_set(value: Any) -> bool:
    """The playbook node can send empty values for the arguments left untouched."""
    return value is not None and value != "" and value != []


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError, TypeError, AttributeError:
        return False


def _error_detail(response: requests.Response) -> str:
    try:
        content = response.json()
    except ValueError:
        return response.text
    if isinstance(content, dict) and "message" in content:
        return str(content["message"])
    return str(content)


class _CaseAction(GenericAPIAction):
    timeout = 60

    # argument -> (listing route, query parameters, name of the object in error messages)
    NAMED_REFERENCES: ClassVar[dict[str, tuple[str, dict[str, str], str]]] = {
        "custom_status_uuid": ("custom_statuses", {"match[type]": "case", "with_is_used": "false"}, "status"),
        "custom_priority_uuid": ("custom_priorities", {"with_is_used": "false"}, "priority"),
        "verdict_uuid": ("custom_verdicts", {"with_is_used": "false"}, "verdict"),
    }

    @retry(
        reraise=True,
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(max=10),
        stop=stop_after_attempt(5),
    )
    def _call_api(self, verb: str, path: str, **kwargs: Any) -> Any:
        url = urljoin(self.module.configuration["base_url"], base_url + path)
        response = requests.request(verb, url, headers=self.get_headers(), timeout=self.timeout, **kwargs)
        if 400 <= response.status_code < 500:
            raise CaseActionError(
                f"{verb.upper()} {base_url}{path} failed with status {response.status_code}: {_error_detail(response)}"
            )
        response.raise_for_status()
        return response.json() if response.status_code != 204 else None

    def _resolve_named_references(self, arguments: dict) -> None:
        """Replace the names given for the status, the priority and the verdict with their UUIDs."""
        for argument, (route, params, kind) in self.NAMED_REFERENCES.items():
            name = arguments.get(argument)
            if not _is_set(name) or not isinstance(name, str) or _is_uuid(name):
                continue

            items = (self._call_api("get", route, params=params) or {}).get("items", [])
            matches = [item for item in items if str(item.get("label", "")).casefold() == name.strip().casefold()]
            if len(matches) > 1:
                candidates = ", ".join(f"{item['label']} ({item['uuid']})" for item in matches)
                raise CaseActionError(f"Several case {kind} values are named '{name}': {candidates}. Use the UUID")
            if not matches:
                valid = ", ".join(sorted(str(item.get("label")) for item in items)) or "none"
                raise CaseActionError(f"Unknown case {kind} '{name}'. Valid names: {valid}")

            arguments[argument] = str(matches[0]["uuid"])

    @staticmethod
    def _complete_subscribers(arguments: dict, assignees: list[str] | None = None) -> None:
        """Default the subscription type, which can only be `assignee`, and append the assignees."""
        if not _is_set(arguments.get("subscribers")) and not assignees:
            return

        subscribers = [
            {"avatar_uuid": subscriber, "type": ASSIGNEE}
            if isinstance(subscriber, str)
            else {**subscriber, "type": subscriber.get("type") or ASSIGNEE}
            for subscriber in arguments.get("subscribers") or []
        ]
        known = {subscriber.get("avatar_uuid") for subscriber in subscribers}
        subscribers.extend(
            {"avatar_uuid": avatar_uuid, "type": ASSIGNEE}
            for avatar_uuid in dict.fromkeys(assignees or [])
            if avatar_uuid not in known
        )
        arguments["subscribers"] = subscribers

    def _prepare(self, arguments: dict) -> None:
        """Rewrite the arguments in place before they are sent to the API."""
        self._resolve_named_references(arguments)

    def _finalize(self, arguments: dict, case: dict) -> dict:
        """Run the follow-up calls once the case is created or updated."""
        return case

    def run(self, arguments: dict) -> dict | None:
        try:
            self._prepare(arguments)
        except (CaseActionError, requests.RequestException) as exc:
            self.error(str(exc))
            return None

        case = super().run(arguments)
        if case is None:
            return None

        return self._finalize(arguments, case)


class CreateCase(_CaseAction):
    verb = "post"
    endpoint = base_url + "cases"
    query_parameters: ClassVar[list[str]] = []

    def _prepare(self, arguments: dict) -> None:
        self._template_uuid = arguments.pop("template_uuid", None)
        self._complete_subscribers(arguments, arguments.pop("assignees", None))
        super()._prepare(arguments)

    def _finalize(self, arguments: dict, case: dict) -> dict:
        if not _is_set(self._template_uuid):
            return case

        try:
            self._call_api("post", f"case-templates/{self._template_uuid}/apply", json={"uuids": [case["uuid"]]})
        except (CaseActionError, requests.RequestException) as exc:
            # The case exists: return it so the playbook can still use it, but flag the run as failed
            self.error(f"Case {case.get('short_id')} was created, but the template could not be applied: {exc}")
            return case

        # Read the case again to return the custom fields set by the template
        try:
            return self._call_api("get", f"cases/{case['uuid']}")
        except (CaseActionError, requests.RequestException) as exc:
            self.log(f"Template applied, but the case could not be read again: {exc}", level="warning")
            return case


class UpdateCase(_CaseAction):
    verb = "patch"
    endpoint = base_url + "cases/{uuid}"
    query_parameters: ClassVar[list[str]] = []

    def _prepare(self, arguments: dict) -> None:
        self._complete_subscribers(arguments)
        super()._prepare(arguments)
