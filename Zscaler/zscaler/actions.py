from abc import ABC
from collections import defaultdict
from functools import cached_property
from typing import Any

import requests
from sekoia_automation.action import Action

from .client import ApiClient
from .helpers import stix_to_indicators


class ZscalerBaseAction(Action, ABC):
    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(
            cloud_name=self.module.configuration["base_url"],
            api_key=self.module.configuration["api_key"],
            username=self.module.configuration["username"],
            password=self.module.configuration["password"],
        )

    @property
    def base_url(self) -> str:
        return self.client.base_url

    def process_response(self, response: requests.Response) -> None:
        if not response.ok:
            message = f"Request on Zscaler API failed with status {response.status_code} - {response.text}"
            self.log(message=message, level="error")

            response.raise_for_status()

    def get_valid_indicators_from_list(self, arguments) -> list:
        single_ioc = arguments.get("IoC")
        multiple_iocs = arguments.get("IoCs")

        IOC_list = []

        if single_ioc:
            IOC_list.append(single_ioc)

        if multiple_iocs:
            IOC_list.extend(multiple_iocs)

        self.log(f"IOC_list to block {IOC_list}", level="info")
        return IOC_list

    def get_valid_indicators_from_stix(self, stix_objects):
        """
        Transform the IOC from the STIX format to the payload expected by Zscaler
        """
        ZSCALER_IOC_TYPE: dict[str, dict[str, str]] = {
            "ipv4-addr": {"value": "ipv4"},
            "ipv6-addr": {"value": "ipv6"},
            "domain-name": {"value": "domain"},
            "url": {"value": "url"},
        }
        seen_values = defaultdict(list)
        results = {"valid": [], "revoked": []}
        try:
            for object in stix_objects:
                # Extract value and type from pattern
                indicators = stix_to_indicators(stix_object=object, supported_types_map=ZSCALER_IOC_TYPE)
                for indicator in indicators:
                    ioc_value = indicator["value"]
                    ioc_type = indicator["type"]
                    if ioc_type in ZSCALER_IOC_TYPE:
                        # Handle revoked objects
                        if object.get("revoked", False):
                            results["revoked"].append(ioc_value)
                            continue

                        # Ignore this IOC if the same value has already been processed
                        if ioc_value in seen_values[ioc_type]:
                            continue

                        seen_values[ioc_type].append(ioc_value)
                        results["valid"].append(ioc_value)

        except Exception as e:
            self.log_exception(e, message=f"Build of IOC list failed")
        return results

    def post_blacklist_iocs_to_add(self, iocs: list):
        url = f"{self.base_url}/security/advanced/blacklistUrls"
        params = {"action": "ADD_TO_LIST"}
        payload = {"blacklistUrls": iocs}

        response = self.client.post(url, params=params, json=payload, timeout=60)
        self.process_response(response)

        return response.json()

    def post_blacklist_iocs_to_remove(self, iocs: list):
        url = f"{self.base_url}/security/advanced/blacklistUrls"
        params = {"action": "REMOVE_FROM_LIST"}
        payload = {"blacklistUrls": iocs}

        response = self.client.post(url, params=params, json=payload, timeout=60)
        self.process_response(response)

        return response.json()

    def post_activate_changes(self):
        url = f"{self.base_url}/status/activate"

        response = self.client.post(url, timeout=60)
        self.process_response(response)

        return response.json()

    def list_security_blacklisted_urls(self):
        url = f"{self.base_url}/security/advanced"

        response = self.client.get(url, timeout=60)
        self.process_response(response)

        return response.json()


class ZscalerBlockIOC(ZscalerBaseAction):
    def run(self, arguments: Any) -> Any:
        iocs = self.get_valid_indicators_from_list(arguments)
        return self.post_blacklist_iocs_to_add(iocs)


class ZscalerUnBlockIOC(ZscalerBaseAction):
    def run(self, arguments: Any) -> Any:
        iocs = self.get_valid_indicators_from_list(arguments)
        return self.post_blacklist_iocs_to_remove(iocs)


class ZscalerPushIOCBlock(ZscalerBaseAction):
    def run(self, arguments):
        stix_objects = self.json_argument("stix_objects", arguments)
        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")

        indicators = self.get_valid_indicators_from_stix(stix_objects)
        if len(indicators["valid"]) == 0 and len(indicators["revoked"]) == 0:
            self.log("Received indicators were not valid and/or not supported", level="error")
            return None

        response = None

        if len(indicators["valid"]):
            response = self.post_blacklist_iocs_to_add(indicators["valid"])

        if len(indicators["revoked"]):
            response = self.post_blacklist_iocs_to_remove(indicators["revoked"])

        return response


class ZscalerActivateChanges(ZscalerBaseAction):
    def run(self, arguments):
        return self.post_activate_changes()


class ZscalerListBlockedIOC(ZscalerBlockIOC):
    def run(self, arguments):
        return self.list_security_blacklisted_urls()
