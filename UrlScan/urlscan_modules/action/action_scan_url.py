from typing import Any

import httpx
from urlscan import APIError, Client
from urlscan.error import RateLimitRemainingError

from urlscan_modules.action.action_get_scan_result import fetch_scan_summary
from urlscan_modules.base import ActionError, UrlScanAction, describe_error
from urlscan_modules.formatters import blacklisted_summary, submitted_summary
from urlscan_modules.models import ScanUrlArguments
from urlscan_modules.validators import internal_target_reason

POLL_INTERVAL = 2
HINT = 'retrieve it later with "Get scan result"'


def _is_blacklisted(error: APIError) -> bool:
    text = f"{error.message} {error.description or ''}".lower()
    return error.status == 400 and "blacklist" in text


class ScanUrl(UrlScanAction):
    def perform(self, client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
        args = ScanUrlArguments.model_validate(arguments)
        url, tags, timeout, visibility = args.url, args.tags, args.timeout, args.visibility
        country = (args.country or "").lower()
        fail_on_blacklisted_url, wait_for_result = args.fail_on_blacklisted_url, args.wait_for_result

        reason = internal_target_reason(url)
        if reason is not None:
            raise ActionError(reason)

        # A submission is not idempotent: a repeat could spend a second scan of the quota.
        try:
            submission = self.call(
                client.scan,
                url,
                visibility=visibility,
                tags=tags or None,
                customagent=args.customagent,
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
