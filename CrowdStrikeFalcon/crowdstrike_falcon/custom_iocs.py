from collections import defaultdict
from datetime import date, timedelta
from posixpath import join as urljoin
from typing import Dict, List

from crowdstrike_falcon.action import CrowdstrikeAction
from crowdstrike_falcon.helpers import stix_to_indicators


class CrowdstrikeActionIOC(CrowdstrikeAction):
    ACTION = "no_action"
    DEFAULT_SEVERITY = "high"
    DEFAULT_PLATFORMS = ["mac", "windows", "linux"]
    DEFAULT_TAGS = ["Sekoia.io"]
    DEFAULT_SOURCE = "Sekoia.io"

    def get_payload(self, value, type):
        return {
            "value": value,
            "type": type,
            "action": self.ACTION,
            "severity": self.DEFAULT_SEVERITY,
            "platforms": self.DEFAULT_PLATFORMS,
            "tags": self.DEFAULT_TAGS,
            "source": self.DEFAULT_SOURCE,
            "applied_globally": True,
        }

    def remove_indicators(self, indicators: list):
        ids_to_remove = []
        # Get the indicator IDs in Crowdstrike
        for indicator in indicators:
            fql_filter = f"value:\"{indicator['value']}\""
            result = next(self.client.find_indicators(fql_filter=fql_filter))
            if result:
                ids_to_remove.append(result)
            else:
                self.log(f"IOC with value {indicator['value']} not found, skipping delete")

        # Delete the IOCs in Crowdstrike
        if len(ids_to_remove) > 0:
            self.log(f"Removing {len(ids_to_remove)} existing indicators from Crowdstrike Falcon")
            next(self.client.delete_indicators(ids_to_remove))

    def remove_expired_indicators(self):
        ids_to_remove = []

        for result in self.client.find_indicators(fql_filter=f"source:'{self.DEFAULT_SOURCE}'+expired:true"):
            ids_to_remove.append(result)

            # Delete the IOCs in Crowdstrike
            if len(ids_to_remove) > 1000:
                self.log(f"Removing {len(ids_to_remove)} existing indicators from Crowdstrike Falcon")
                next(self.client.delete_indicators(ids_to_remove))
                ids_to_remove = []

        # Delete the IOCs in Crowdstrike
        if len(ids_to_remove) > 0:
            self.log(f"Removing {len(ids_to_remove)} existing indicators from Crowdstrike Falcon")
            next(self.client.delete_indicators(ids_to_remove))

    def remove_old_indicators(self, valid_for):
        ids_to_remove = []

        for result in self.client.find_indicators(
            fql_filter=f"source:'{self.DEFAULT_SOURCE}'+modified_on:<='{date.today() - timedelta(days=valid_for)}'"
        ):
            ids_to_remove.append(result)

            # Delete the IOCs in Crowdstrike
            if len(ids_to_remove) > 1000:
                self.log(f"Removing {len(ids_to_remove)} existing indicators from Crowdstrike Falcon")
                next(self.client.delete_indicators(ids_to_remove))
                ids_to_remove = []

        # Delete the IOCs in Crowdstrike
        if len(ids_to_remove) > 0:
            self.log(f"Removing {len(ids_to_remove)} existing indicators from Crowdstrike Falcon")
            next(self.client.delete_indicators(ids_to_remove))

    def create_indicators(self, indicators: list):
        if len(indicators) > 0:
            self.log(f"Pushing {len(indicators)} new indicators to Crowdstrike Falcon")
            next(self.client.upload_indicators(indicators=indicators))


class CrowdstrikeActionPushIOCs(CrowdstrikeActionIOC):
    DEFAULT_SEKOIA_BASE_URL = "https://app.sekoia.io"
    SUPPORTED_TYPES_MAP: Dict[str, Dict[str, str]] = {}
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

    def get_reference_url(self, id):
        return urljoin(self.sekoia_base_url, f"intelligence/objects/{id}")

    def get_valid_indicators(self, stix_objects):
        """
        Transform the IOC from the STIX format to the payload expected by Crowdstrike Falcon
        """

        seen_values = defaultdict(list)
        results = {"valid": [], "revoked": []}
        for object in stix_objects:
            # Extract value and type from pattern
            self.log(message=f"object in stix_objects {str(object)}", level="debug")
            indicators = stix_to_indicators(stix_object=object, supported_types_map=self.SUPPORTED_TYPES_MAP)
            for indicator in indicators:
                ioc_value = indicator["value"]
                ioc_type = indicator["type"]
                result = self.get_payload(value=ioc_value, type=ioc_type)

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
                    result["expiration"] = valid_until

                # Add a direct link in description if the data is originating from Sekoia.io
                if "x_ic_observable_types" in object.keys():
                    result["description"] = self.get_reference_url(object["id"])

                seen_values[ioc_type].append(ioc_value)
                results["valid"].append(result)

        return results

    def run(self, arguments):
        if arguments.get("sekoia_base_url"):
            self.sekoia_base_url = arguments.get("sekoia_base_url")

        # Cleanup expired and old indicators before proceeding with adding new ones
        # in case we are near the limit in CrowdStrike
        valid_for = arguments.get("valid_for", 0)
        self.remove_expired_indicators()
        if valid_for > 0:
            self.remove_old_indicators(valid_for)

        stix_objects = self.json_argument("stix_objects", arguments)
        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")
        indicators = self.get_valid_indicators(stix_objects)
        if len(indicators["valid"]) == 0 and len(indicators["revoked"]) == 0:
            self.log("Received indicators were not valid and/or not supported")
            return
        # Remove revoked indicators before proceeding with adding new ones
        # in case we are near the limit in CrowdStrike
        self.remove_indicators(indicators["revoked"])
        self.create_indicators(indicators["valid"])


class CrowdstrikeActionPushIOCsBlock(CrowdstrikeActionPushIOCs):
    ACTION = "prevent"
    SUPPORTED_TYPES_MAP = {
        "file": {"hashes.MD5": "md5", "hashes.SHA-256": "sha256"},
    }


class CrowdstrikeActionPushIOCsDetect(CrowdstrikeActionPushIOCs):
    ACTION = "detect"
    SUPPORTED_TYPES_MAP = {
        "ipv4-addr": {"value": "ipv4"},
        "ipv6-addr": {"value": "ipv6"},
        "domain-name": {"value": "domain"},
        "file": {"hashes.MD5": "md5", "hashes.SHA-256": "sha256"},
    }


class CrowdstrikeActionAddIOC(CrowdstrikeActionIOC):
    SUPPORTED_TYPES: List[str] = []
    ACTION = ""

    def run(self, arguments):
        ioc_value = arguments.get("value", "")
        ioc_type = arguments.get("type", "").lower()
        if ioc_type not in self.SUPPORTED_TYPES:
            self.error(f"Type {ioc_type} is not supported. Refer to the documentation for supported types.")
            return
        self.log(f"Pushing {ioc_type} {ioc_value} with action {self.ACTION} to Crowdstrike Falcon")
        self.create_indicators(indicators=[self.get_payload(value=ioc_value, type=ioc_type)])


class CrowdstrikeActionBlockIOC(CrowdstrikeActionAddIOC):
    SUPPORTED_TYPES = ["md5", "sha256"]
    ACTION = "prevent"


class CrowdstrikeActionMonitorIOC(CrowdstrikeActionAddIOC):
    SUPPORTED_TYPES = ["md5", "sha256", "ipv4", "ipv6", "domain"]
    ACTION = "detect"
