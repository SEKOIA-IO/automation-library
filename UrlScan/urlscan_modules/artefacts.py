"""Checks whether urlscan.io still stores the screenshot and the DOM of a scan."""

from collections.abc import Callable
from typing import Any

import httpx
from urlscan import APIError, Client

from urlscan_modules.base import UrlScanAction


def is_stored(fetch: Callable[[str], Any], scan_id: str) -> tuple[bool | None, int | None]:
    """Fetch an artefact once, without retries: (stored, status of the error).

    A 404 means the artefact is not stored. Any other failure leaves the answer unknown.
    """
    try:
        fetch(scan_id)
    except APIError as error:
        return (False, 404) if error.status == 404 else (None, error.status)
    except httpx.TransportError:
        return None, None
    return True, None


def apply_availability(action: UrlScanAction, client: Client, summary: dict[str, Any]) -> None:
    """Fill the `*_available` flags of a summary and drop the link of an artefact that is not stored."""
    scan_id = summary["uuid"]
    for name, fetch in (("screenshot", client.get_screenshot), ("dom", client.get_dom)):
        stored, status = is_stored(fetch, scan_id)
        summary[f"{name}_available"] = stored
        if stored is False:
            summary[f"{name}_url"] = None
        elif stored is None:
            reason = f"status {status}" if status is not None else "network error"
            label = "DOM" if name == "dom" else name
            # Only the status is logged: the body of a 404 screenshot is a binary placeholder.
            action.log(f"Could not check the {label} of scan {scan_id} ({reason})", level="warning")
