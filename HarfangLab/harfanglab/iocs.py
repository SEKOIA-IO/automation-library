# coding: utf-8
from collections import defaultdict
from datetime import datetime, timezone
from functools import cached_property
from typing import Any
from urllib.parse import urljoin

from dateutil.parser import isoparse
from requests import Response
from sekoia_automation.action import Action

from .client import ApiClient
from .helpers import stix_to_indicators
from .logging import get_logger

logger = get_logger()


class CreateIOCs(Action):
    DEFAULT_SEKOIA_BASE_URL = "https://app.sekoia.io"
    SUPPORTED_TYPES_MAP: dict[str, dict[str, str]] = {
        "ipv4-addr": {"value": "ip_both"},
        "ipv6-addr": {"value": "ip_both"},
        "domain-name": {"value": "domain_name"},
        "file": {"hashes.MD5": "hash", "hashes.SHA1": "hash", "hashes.sha256": "hash"},
        "url": {"value": "url"},
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sekoia_base_url = self.DEFAULT_SEKOIA_BASE_URL

    @cached_property
    def client(self):
        return ApiClient(instance_url=self.module.configuration["url"], token=self.module.configuration["api_token"])

    def _handle_response_error(self, response: Response) -> None:
        if not response.ok:
            logger.error(
                "Failed request to HarfangLab API",
                status_code=response.status_code,
                reason=response.reason,
                error=response.content,
            )

            message = f"Request to HarfangLab API failed with status {response.status_code} - {response.reason}"
            self.log(message=message, level="error")
            response.raise_for_status()

    def api_delete_indicator(self, indicator_id: str) -> Response:
        response = self.client.delete(
            f"{self.client.instance_url}/api/data/threat_intelligence/IOCRule/{indicator_id}", timeout=60
        )
        self._handle_response_error(response)
        return response

    def api_search_indicator(self, indicator_value: str, source_id: str) -> Response:
        response = self.client.get(
            f"{self.client.instance_url}/api/data/threat_intelligence/IOCRule/",
            params={"search": indicator_value, "source_id": source_id},
            timeout=60,
        )
        self._handle_response_error(response)
        return response

    def api_create_indicator(self, indicator: dict[str, Any]) -> Response:
        # NOTE: unlike methods before, this function doesn't raise an exception in case of HTTP error
        response = self.client.post(
            f"{self.client.instance_url}/api/data/threat_intelligence/IOCRule/", json=indicator, timeout=60
        )
        return response

    def get_reference_url(self, id) -> str:
        return urljoin(self.sekoia_base_url, f"intelligence/objects/{id}")

    @staticmethod
    def get_payload(value: Any, type: Any, args: dict[str, Any]):
        return {
            "source_id": args["source_id"],
            "type": type,
            "value": value,
            "block_on_agent": args["block_on_agent"],
            "quarantine_on_agent": args["quarantine_on_agent"],
            "endpoint_detection": args["detect_on_agent"],
            "enabled": True,
        }

    def get_valid_indicators(self, stix_objects: Any, args: dict[str, Any]) -> dict[Any, Any]:
        """
        Transform the IOC from the STIX format to the payload expected by HarfangLab
        """

        seen_values: defaultdict[str, list[str]] = defaultdict(list)
        results: dict[str, Any] = {"valid": [], "revoked": [], "expired": []}

        for object in stix_objects:
            # Extract value and type from pattern
            self.log(message=f"object in stix_objects {str(object)}", level="debug")
            indicators = stix_to_indicators(stix_object=object, supported_types_map=self.SUPPORTED_TYPES_MAP)
            for indicator in indicators:
                ioc_value = indicator["value"]
                ioc_type = indicator["type"]
                result = self.get_payload(value=ioc_value, type=ioc_type, args=args)

                # Handle revoked objects
                if object.get("revoked", False):
                    results["revoked"].append(result)
                    continue

                # Ignore this IOC if the same value has already been processed
                if ioc_value in seen_values[ioc_type]:
                    continue

                # Add a direct link in description if the data is originating from Sekoia.io
                if "x_ic_observable_types" in object.keys():
                    result["description"] = self.get_reference_url(object["id"])

                # Compare expiration data if exists
                valid_until = object.get("valid_until")
                if valid_until:
                    current_datetime = datetime.now(timezone.utc)
                    valid_until_datetime = isoparse(valid_until)
                    if valid_until_datetime < current_datetime:
                        results["expired"].append(result)
                        continue

                seen_values[ioc_type].append(ioc_value)
                results["valid"].append(result)

        return results

    def delete_indicator_by_ids(self, indicator_ids: list[str]) -> None:
        self.log(f"Removing {len(indicator_ids)} indicators from HarfangLab", level="info")

        for indicator_id in indicator_ids:
            self.api_delete_indicator(indicator_id=indicator_id)

    def remove_indicators(self, indicators: list) -> None:
        ids_to_remove = []

        if len(indicators) > 0:
            for indicator in indicators:
                response = self.api_search_indicator(
                    indicator_value=indicator["value"], source_id=indicator["source_id"]
                )
                found_ids = [item["id"] for item in response.json().get("results", [])]
                ids_to_remove.extend(found_ids)

        if len(ids_to_remove) > 0:
            self.delete_indicator_by_ids(indicator_ids=ids_to_remove)

    def create_indicators(self, indicators: list) -> None:
        if len(indicators) > 0:
            self.log(f"Pushing {len(indicators)} new indicators to HarfangLab", level="info")
            for ioc in indicators:
                response = self.api_create_indicator(indicator=ioc)
                if response.status_code == 400:
                    # we could get this error if the ioc rule with
                    # this type, value and source already exists
                    if "already exists" in response.text:
                        self.log("Ioc rule with this Type, Value and Source already exists.", level="info")
                        logger.info(
                            "Ioc rule with this Type, Value and Source already exists.",
                            type=ioc["type"],
                            value=ioc["value"],
                            source=ioc["source_id"],
                        )
                        continue

                self._handle_response_error(response)

    def run(self, arguments: Any) -> Any:
        if arguments.get("sekoia_base_url"):
            self.sekoia_base_url = arguments.get("sekoia_base_url")

        stix_objects = self.json_argument("stix_objects", arguments)
        if stix_objects is None or len(stix_objects) == 0:
            # Cleanup expired indicators before proceeding with adding new ones
            self.log("Received stix_objects were empty", level="info")

        indicators = self.get_valid_indicators(stix_objects, args=arguments)
        if len(indicators["valid"]) == 0 and len(indicators["revoked"]) == 0 and len(indicators["expired"]) == 0:
            self.log("Received indicators were not valid and/or not supported", level="info")
            return

        # Remove revoked and expired indicators before proceeding with adding new ones
        self.remove_indicators(indicators["revoked"])
        self.remove_indicators(indicators["expired"])
        self.create_indicators(indicators["valid"])
