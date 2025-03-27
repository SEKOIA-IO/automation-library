from collections import defaultdict
from typing import Dict
from zscaler.helpers import stix_to_indicators

from sekoia_automation.action import Action
from zscaler_api_talkers import ZiaTalker
from requests.exceptions import JSONDecodeError


class ZscalerAction(Action):
    def zia_auth(self):
        try:
            return ZiaTalker(
                cloud_name=self.module.configuration["base_url"],
                api_key=self.module.configuration["api_key"],
                username=self.module.configuration["username"],
                password=self.module.configuration["password"],
            )

        except Exception as e:
            self.log(f"ZIA authentication failed", level="critical")
            self.log_exception(e)
            raise

    def get_valid_indicators_from_list(self, arguments) -> list:
        try:
            IOC_list = [arguments["IoC"]]
            self.log(f"IOC_list to block {IOC_list}")
            return IOC_list

        except Exception as e:
            self.log(f"Build of IOC list failed: {str(e)}", level="error")
            return []

    def get_valid_indicators_from_stix(self, stix_objects):
        """
        Transform the IOC from the STIX format to the payload expected by Zscaler
        """
        ZSCALER_IOC_TYPE: Dict[str, Dict[str, str]] = {
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

    def post_blacklist_iocs_to_add(self, IOC_list: list):
        api = self.zia_auth()
        raw_response = api.add_security_blacklist_urls(urls=IOC_list)
        try:
            response = raw_response.json()
        except JSONDecodeError as e:
            return None
        return response

    def post_blacklist_iocs_to_remove(self, IOC_list: list):
        api = self.zia_auth()
        try:
            response = api.remove_security_blacklist_urls(urls=IOC_list)
        except JSONDecodeError as e:
            return None
        return response

    def list_security_blacklisted_urls(self):
        api = self.zia_auth()
        response = api.list_security_blacklisted_urls()
        return response


class ZscalerListBLockIOC(ZscalerAction):
    def run(self):
        response = self.list_security_blacklisted_urls()
        return response


class ZscalerBlockIOC(ZscalerAction):
    def run(self, arguments):
        IOC_list = self.get_valid_indicators_from_list(arguments)
        response = self.post_blacklist_iocs_to_add(IOC_list)
        return response


class ZscalerUnBlockIOC(ZscalerAction):
    def run(self, arguments):
        IOC_list = self.get_valid_indicators_from_list(arguments)
        response = self.post_blacklist_iocs_to_remove(IOC_list)
        return response


class ZscalerPushIOCBlock(ZscalerAction):
    def run(self, arguments):
        if arguments.get("sekoia_base_url"):
            self.sekoia_base_url = arguments.get("sekoia_base_url")

        stix_objects = self.json_argument("stix_objects", arguments)
        if stix_objects is None or len(stix_objects) == 0:
            self.log("Received stix_objects were empty")

        indicators = self.get_valid_indicators_from_stix(stix_objects)
        if len(indicators["valid"]) == 0 and len(indicators["revoked"]) == 0:
            self.log("Received indicators were not valid and/or not supported")
            return None

        else:
            if len(indicators["valid"]):
                response = self.post_blacklist_iocs_to_add(indicators["valid"])
            if len(indicators["revoked"]):
                response = self.post_blacklist_iocs_to_remove(indicators["revoked"])
            return response
