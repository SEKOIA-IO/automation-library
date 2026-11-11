import time
from typing import Any

from urlscan import APIError, Client

from urlscan_modules.artefacts import apply_availability
from urlscan_modules.base import ActionError, UrlScanAction
from urlscan_modules.comment import build_comment
from urlscan_modules.formatters import build_scan_summary
from urlscan_modules.validators import valid_scan_id

# Right after a scan completes, urlscan.io may answer without the `lists` section.
MAX_LISTS_REFETCHES = 3
LISTS_REFETCH_DELAY = 5


def fetch_scan_summary(
    action: UrlScanAction, client: Client, scan_id: str, submission: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The summary of a finished scan, with artefact availability and the Markdown comment."""
    result = action.call(client.get_result, scan_id)
    for _ in range(MAX_LISTS_REFETCHES):
        if "lists" in result:
            break
        time.sleep(LISTS_REFETCH_DELAY)
        result = action.call(client.get_result, scan_id)

    summary = build_scan_summary(result, action.base_url, submission)
    apply_availability(action, client, summary)
    summary["comment"] = build_comment(summary)
    return summary


class GetScanResult(UrlScanAction):
    def perform(self, client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
        scan_id = valid_scan_id(arguments.get("scan_id"))
        try:
            return fetch_scan_summary(self, client, scan_id)
        except APIError as error:
            if error.status == 404:
                raise ActionError(f"Scan {scan_id} not found or not finished yet") from error
            if error.status == 410:
                raise ActionError(f"Scan {scan_id} has been deleted") from error
            raise
