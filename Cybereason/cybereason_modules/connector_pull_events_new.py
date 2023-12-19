from typing import Any
from posixpath import join as urljoin

import requests

from cybereason_modules.connector_pull_events import CybereasonEventConnector
from cybereason_modules.constants import MALOP_GET_ALL_ENDPOINT
from cybereason_modules.logging import get_logger
from cybereason_modules.exceptions import InvalidResponse

logger = get_logger()


def adapt_malops_to_legacy(ops: list[dict]):
    def replace_items_in_dict(key_to_key: dict, d: dict) -> dict:
        return {key_to_key.get(k, k): v for k, v in d.items()}

    res = []
    for item in ops:
        malop = replace_items_in_dict({"isEdr": "edr"}, item)
        malop["@class"] = ".MalopInboxModel"
        res.append(malop)

    return res


class CybereasonEventConnectorNew(CybereasonEventConnector):
    """
    Using a new endpoint /rest/mmng/v2/malops for getting a list of malops
    """

    def fetch_malops(self, from_date: int, to_date: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "search": {},
            "range": {"from": from_date, "to": to_date},
            "pagination": {"pageSize": self.configuration.chunk_size, "offset": 0},
            "federation": {"groups": []},
            "sort": [{"field": "LastUpdateTime", "order": "asc"}],
        }

        if self.configuration.group_ids is not None:
            params["federation"]["groups"] = self.configuration.group_ids

        url = urljoin(self.module.configuration.base_url, MALOP_GET_ALL_ENDPOINT)

        try:
            response = self.client.post(url, json=params, timeout=60)

            if not response.ok:
                logger.error(
                    "Failed to fetch events from the Cybereason API",
                    status_code=response.status_code,
                    reason=response.reason,
                    error=response.content,
                )
                self.log(
                    message=(
                        f"Request on Cybereason API to fetch events failed with status {response.status_code}"
                        f" - {response.reason}"
                    ),
                    level="error",
                )
                return []

            else:
                content = self.parse_response_content(response)
                malops = content.get("data", {}).get("data")

                if malops is None:
                    raise InvalidResponse(response)

                # Change back fields names to use the same code
                malops = adapt_malops_to_legacy(malops)

                self.log(
                    message=f"Retrieved {len(malops)} events from Cybereason API with status {response.status_code}",
                    level="debug",
                )
                return malops

        except requests.Timeout as error:
            raise TimeoutError(url) from error
