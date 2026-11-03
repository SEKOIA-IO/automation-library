"""Create or update case: find the case of an external incident and update it, or create it.

The incident is identified by the tag `ext:<source>:<external_id>` on its case:

- an open case with this tag is updated: the priority can only go up, the tags are added, the empty custom fields
  are filled and the comment is posted. Its status never changes.
- a closed case with this tag only gets the comment, and stays closed.
- otherwise a case is created with this tag.
"""

from typing import Any

import requests

from sekoiaio.operation_center.cases import CaseActionError, CaseAPIClient, _is_set

# Legacy status of the closed cases, used when a case has no custom status
CLOSED_STATUS_UUID = "b3ccefdb-5c61-4604-bc26-b370a1c0b2e5"


class CreateOrUpdateCase(CaseAPIClient):
    def run(self, arguments: dict) -> dict | None:
        try:
            return self._create_or_update(arguments)
        except (CaseActionError, requests.RequestException) as exc:
            self.error(str(exc))
            return None

    @staticmethod
    def incident_tag(source: str, external_id: str) -> str:
        # The tag filter of the Cases API splits its value on commas
        return f"ext:{source.strip()}:{external_id.strip()}".replace(",", "%2C")

    def _create_or_update(self, arguments: dict) -> dict:
        source, external_id = arguments.get("source"), arguments.get("external_id")
        if not _is_set(source) or not _is_set(external_id):
            raise CaseActionError("`source` and `external_id` are required to identify the incident")
        tag = self.incident_tag(str(source), str(external_id))
        community_uuid = arguments.get("community_uuid") or None

        # Resolve the names before any change, so that a wrong name changes nothing
        references = {"custom_priority_uuid": arguments.get("priority")}
        self._resolve_named_references(references)
        priority_uuid = references["custom_priority_uuid"] if _is_set(references["custom_priority_uuid"]) else None
        custom_fields = self._resolve_custom_fields(arguments.get("custom_fields") or {})

        cases = self._find_cases(tag, community_uuid)
        open_case = next((case for case in cases if not self._is_closed(case)), None)
        if open_case is not None:
            return self._update(open_case, arguments, priority_uuid, custom_fields)
        if cases:
            return self._comment_closed_case(cases[-1], arguments)
        return self._create(arguments, tag, community_uuid, priority_uuid, custom_fields)

    def _find_cases(self, tag: str, community_uuid: str | None) -> list[dict]:
        """Cases with the incident tag, oldest first."""
        params = {
            "match[tags]": tag,
            "match[type]": "manual,automatic",
            "with_custom_statuses": "true",
            "sort": "created_at",
            "direction": "asc",
            "limit": 100,
        }
        if community_uuid:
            params["match[community_uuid]"] = community_uuid
        return (self._call_api("get", "cases", params=params) or {}).get("items") or []

    @staticmethod
    def _is_closed(case: dict) -> bool:
        if stage := (case.get("custom_status") or {}).get("stage"):
            return stage == "closed"
        return str(case.get("status_uuid")) == CLOSED_STATUS_UUID

    def _create(
        self,
        arguments: dict,
        tag: str,
        community_uuid: str | None,
        priority_uuid: str | None,
        custom_fields: list[dict],
    ) -> dict:
        if not _is_set(arguments.get("title")):
            raise CaseActionError("`title` is required to create the case of a new incident")

        body: dict[str, Any] = {
            "title": arguments["title"],
            "tags": self._merge_tags([tag], arguments.get("tags") or []),
        }
        if _is_set(arguments.get("description")):
            body["description"] = arguments["description"]
        if priority_uuid:
            body["custom_priority_uuid"] = priority_uuid
        if community_uuid:
            body["community_uuid"] = community_uuid
        if custom_fields:
            body["custom_fields"] = custom_fields
        self._complete_subscribers(body, arguments.get("assignees"))

        case = self._call_api("post", "cases", json=body)
        if _is_set(arguments.get("template_uuid")):
            case = self._apply_template(
                case, arguments["template_uuid"], "running the action again would update this case without it"
            )
        return self._result(case, "created", None)

    def _update(self, case: dict, arguments: dict, priority_uuid: str | None, custom_fields: list[dict]) -> dict:
        changes: dict[str, Any] = {}
        if priority_uuid and self._raises_priority(case, priority_uuid):
            changes["custom_priority_uuid"] = priority_uuid
        tags = self._merge_tags(case.get("tags") or [], arguments.get("tags") or [])
        # Only send the tags when they change: the Cases API announces a tag change for any tags it receives
        if len(tags) != len(case.get("tags") or []):
            changes["tags"] = tags
        if changes:
            self._call_api("patch", f"cases/{case['uuid']}", json=changes)

        if filled := self._fill_empty_custom_fields(case, custom_fields):
            self._call_api("patch", f"cases/{case['uuid']}/custom-fields", json={"custom_fields": filled})

        self._post_comment(case, arguments)
        return self._result(self._call_api("get", f"cases/{case['uuid']}"), "updated", "external_id")

    def _comment_closed_case(self, case: dict, arguments: dict) -> dict:
        self._post_comment(case, arguments)
        return self._result(self._call_api("get", f"cases/{case['uuid']}"), "updated", "external_id")

    def _post_comment(self, case: dict, arguments: dict) -> None:
        if _is_set(arguments.get("comment")):
            self._call_api("post", f"cases/{case['uuid']}/comments", json={"content": arguments["comment"]})

    def _raises_priority(self, case: dict, priority_uuid: str) -> bool:
        """Whether the priority is higher than the one of the case. The lowest level is the highest priority."""
        priorities = (self._call_api("get", "custom_priorities", params={"with_is_used": "false"}) or {}).get("items")
        levels = {str(priority["uuid"]): priority.get("level") for priority in priorities or []}
        new_level = levels.get(priority_uuid)
        current_level = levels.get(str(case.get("custom_priority_uuid")))
        if new_level is None:
            raise CaseActionError(f"Unknown case priority '{priority_uuid}'")
        return current_level is None or new_level < current_level

    @staticmethod
    def _merge_tags(tags: list[str], new_tags: list[str]) -> list[str]:
        """Add the new tags to the tags, ignoring the case like the Cases API."""
        known = {tag.casefold() for tag in tags}
        added = [str(tag) for tag in dict.fromkeys(new_tags) if _is_set(tag) and str(tag).casefold() not in known]
        return [*tags, *added]

    @staticmethod
    def _fill_empty_custom_fields(case: dict, custom_fields: list[dict]) -> list[dict] | None:
        """All the custom fields of the case, with the empty ones filled, or None when none was empty.

        The API replaces the whole set of custom fields, so the current ones are sent back with the new values.
        """
        current = {str(field["uuid"]): field.get("value") for field in case.get("custom_fields") or []}
        filled = {
            field["uuid"]: field["value"]
            for field in custom_fields
            if _is_set(field["value"]) and not _is_set(current.get(field["uuid"]))
        }
        if not filled:
            return None
        return [{"uuid": uuid, "value": value} for uuid, value in {**current, **filled}.items()]

    @staticmethod
    def _result(case: dict, outcome: str, matched_by: str | None) -> dict:
        return {
            "case_uuid": case["uuid"],
            "short_id": case["short_id"],
            "outcome": outcome,
            "matched_by": matched_by,
            "case": case,
        }
