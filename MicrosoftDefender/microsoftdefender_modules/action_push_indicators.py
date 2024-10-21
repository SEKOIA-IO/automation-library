from collections import defaultdict
from typing import Any
from urllib.parse import urljoin

from requests import Response

from .action_base import MicrosoftDefenderBaseAction
from .helpers import stix_to_indicators


class PushIndicatorsAction(MicrosoftDefenderBaseAction):
    DEFAULT_SEKOIA_BASE_URL = "https://app.sekoia.io"
    SUPPORTED_TYPES_MAP: dict[str, dict[str, str]] = {
        "ipv4-addr": {"value": "IpAddress"},
        "ipv6-addr": {"value": "IpAddress"},
        "domain-name": {"value": "DomainName"},
        "file": {"hashes.MD5": "FileMd5", "hashes.SHA1": "FileSha1", "hashes.sha256": "FileSha256"},
        "url": {"value": "Url"},
    }
    """
    SUPPORTED_TYPES_MAP is used to define the mapping from STIX pattern
    to the different IOCs types supported by Crowdstrike Falcon.
    "stix_root_key": {"stix_sub_key": "target_type"}
    Example with ipv4:
    Mapping with "ipv4-addr": {"value": "ipv4"} for IOC "[ipv4-addr:value = 'X.X.X.X']"
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sekoia_base_url = self.DEFAULT_SEKOIA_BASE_URL

    def list_indicators(self, q: str | None = None) -> Response:
        url = urljoin(self.client.base_url, "api/indicators")
        if q:
            url = url + "?$filter=" + q

        return self.client.get(url)

    def import_indicators(self, indicators: list[dict[str, Any]]) -> Response:
        url = urljoin(self.client.base_url, "api/indicators/import")
        return self.client.post(url, json={"Indicators": indicators})

    def delete_indicators_by_ids(self, indicators_ids: list[str]) -> Response:
        url = urljoin(self.client.base_url, "api/indicators/BatchDelete")
        return self.client.post(url, json={"IndicatorIds": indicators_ids})

    @staticmethod
    def get_payload(value: Any, type: Any, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": "indicator",
            "createdByDisplayName": "Sekoia.io",
            "indicatorType": type,
            "indicatorValue": value,
            "severity": args["severity"],
            "action": args["action"],
            "generateAlert": args["generate_alert"],
        }

    def get_reference_url(self, object_id: str) -> str:
        return urljoin(self.sekoia_base_url, f"intelligence/objects/{object_id}")

    def get_valid_indicators(self, stix_objects: Any, args: dict[str, Any]) -> dict[str, Any]:
        """
        Transform the IOC from the STIX format to the payload expected by Crowdstrike Falcon
        """

        seen_values: dict[str, set[str]] = defaultdict(set)
        results: dict[str, Any] = {"valid": [], "revoked": []}

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

                # Add expiration data if exists
                valid_until = object.get("valid_until")
                if valid_until:
                    result["expirationTime"] = valid_until

                # Add a direct link in description if the data is originating from Sekoia.io
                if "x_ic_observable_types" in object.keys():
                    result["description"] = self.get_reference_url(object["id"])

                seen_values[ioc_type].add(ioc_value)
                results["valid"].append(result)

        return results

    def remove_indicators(self, indicators: list[dict[str, Any]]) -> None:
        indicators_ids = [obj["id"] for obj in indicators]
        if len(indicators_ids) > 0:
            self.log("Removing %d indicators" % len(indicators_ids), level="info")

            response = self.delete_indicators_by_ids(indicators_ids=indicators_ids)
            self.process_response(response)

    def create_indicators(self, indicators: list[dict[str, Any]]) -> None:
        response = self.import_indicators(indicators=indicators)
        self.process_response(response)

    def run(self, arguments: Any) -> Any:
        if arguments.get("sekoia_base_url"):
            self.sekoia_base_url = arguments.get("sekoia_base_url")

        stix_objects = self.json_argument("stix_objects", arguments)
        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")

        indicators = self.get_valid_indicators(stix_objects, arguments)
        if len(indicators["valid"]) == 0 and len(indicators["revoked"]) == 0:
            self.log("Received indicators were not valid and/or not supported")
            return

        # Remove revoked indicators before proceeding with adding new ones
        self.remove_indicators(indicators["revoked"])
        self.create_indicators(indicators["valid"])
