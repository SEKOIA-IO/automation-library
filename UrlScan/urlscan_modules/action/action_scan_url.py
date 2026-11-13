import re
from typing import Any

import httpx
from urlscan import APIError, Client
from urlscan.error import RateLimitRemainingError

from urlscan_modules.action.action_get_scan_result import fetch_scan_summary
from urlscan_modules.base import ActionError, UrlScanAction, describe_error
from urlscan_modules.formatters import blacklisted_summary, submitted_summary
from urlscan_modules.validators import internal_target_reason

DEFAULT_TIMEOUT = 120
MIN_TIMEOUT = 30
MAX_TIMEOUT = 600
MAX_TAGS = 10
POLL_INTERVAL = 2
VISIBILITIES = ("public", "unlisted", "private")
HINT = 'retrieve it later with "Get scan result"'


def _is_blacklisted(error: APIError) -> bool:
    text = f"{error.message} {error.description or ''}".lower()
    return error.status == 400 and "blacklist" in text


class ScanUrl(UrlScanAction):
    def perform(self, client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
        url = (arguments.get("url") or "").strip()
        if not url:
            raise ActionError('"url" is required')
        reason = internal_target_reason(url)
        if reason is not None:
            raise ActionError(reason)

        tags = arguments.get("tags") or []
        if len(tags) > MAX_TAGS:
            raise ActionError(f"At most {MAX_TAGS} tags are allowed, got {len(tags)}")

        country = (arguments.get("country") or "").strip().lower()
        if country and not re.fullmatch(r"[a-z]{2}", country):
            raise ActionError('"country" must be a two-letter ISO 3166-1 alpha-2 code')

        timeout = arguments.get("timeout") or DEFAULT_TIMEOUT
        if not MIN_TIMEOUT <= timeout <= MAX_TIMEOUT:
            raise ActionError(f'"timeout" must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds')

        visibility = arguments.get("visibility") or "private"
        if visibility not in VISIBILITIES:
            raise ActionError(f'"visibility" must be one of {", ".join(VISIBILITIES)}')

        fail_on_blacklisted_url = arguments.get("fail_on_blacklisted_url") is not False
        wait_for_result = arguments.get("wait_for_result") is not False

        # A submission is not idempotent: a repeat could spend a second scan of the quota.
        try:
            submission = self.call(
                client.scan,
                url,
                visibility=visibility,
                tags=tags or None,
                customagent=arguments.get("customagent") or None,
                country=country or None,
                retry_server_errors=False,
            )
        except APIError as error:
            if not fail_on_blacklisted_url and _is_blacklisted(error):
                return blacklisted_summary(url)
            raise
        uuid = submission["uuid"]

        if not wait_for_result:
            return submitted_summary(submission, self.base_url)

        unreachable = False
        try:
            client.wait_for_result(uuid, timeout=timeout, interval=POLL_INTERVAL)
        except TimeoutError:
            pass
        except httpx.TransportError:
            unreachable = True

        try:
            return fetch_scan_summary(self, client, uuid, submission)
        except APIError as error:
            if error.status == 404 and unreachable:
                raise ActionError(
                    f"Scan {uuid} was submitted but urlscan.io could not be reached while waiting; {HINT}"
                ) from error
            if error.status == 404:
                raise ActionError(f"Scan {uuid} did not finish within {timeout} seconds; {HINT}") from error
            if error.status == 410:
                raise ActionError(f"Scan {uuid} has been deleted") from error
            raise self._retrieval_error(uuid, error) from error
        except (RateLimitRemainingError, httpx.TransportError) as error:
            raise self._retrieval_error(uuid, error) from error
        except ActionError as error:
            raise self._retrieval_error(uuid, error) from error

    @staticmethod
    def _retrieval_error(uuid: str, error: Exception) -> ActionError:
        # An ActionError already carries a message meant for the playbook.
        reason = str(error) if isinstance(error, ActionError) else describe_error(error)
        return ActionError(f"Scan {uuid} was submitted but its result could not be retrieved ({reason}); {HINT}")
