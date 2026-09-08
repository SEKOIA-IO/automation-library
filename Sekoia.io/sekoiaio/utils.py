import json
import pathlib
import sys
from datetime import datetime
from functools import cache

from sekoia_automation.action import GenericAPIAction


@cache
def user_agent() -> str:
    version: str = "unknown"

    try:
        manifest = json.load(pathlib.Path("manifest.json").open())
        version = manifest["version"]
    except Exception:
        pass

    return f"symphony-module-sekoia.io/{version}"


def should_patch() -> bool:
    return len(sys.argv) >= 2 and sys.argv[1].endswith("_trigger")


def datetime_to_str(date: datetime) -> str:
    return date.strftime("%Y-%m-%dT%H:%M:%SZ")


class FilteredQueryParametersAction(GenericAPIAction):
    """Base action that only forwards the query parameters the user actually set.

    The playbook node populates every argument declared in the action manifest,
    including empty strings for untouched text filters and ``False`` for
    untouched booleans. The API treats any parameter present in the query
    string as an active filter (e.g. ``match[title]=`` matches nothing,
    ``is_assigned_to_case=false`` excludes assigned alerts), so forwarding these
    unset values makes a search return no results.

    Booleans that were kept are normalized to lowercase ``true`` (``requests``
    would otherwise send Python's ``True``), so the query string matches what
    the API documents and what a browser or curl would send.

    The filtering is applied to what the parent already extracted, so only the
    query parameters the action declares are touched; the remaining arguments
    are left untouched for ``get_body``.
    """

    def get_query_parameters(self, arguments: dict) -> dict | None:
        parameters = super().get_query_parameters(arguments) or {}
        parameters = {
            key: "true" if value is True else value
            for key, value in parameters.items()
            if value is not None and value != "" and value is not False
        }

        return parameters or None
