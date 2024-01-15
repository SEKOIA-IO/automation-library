import requests
import ipaddress
from datetime import datetime, timedelta

from .base import InThreatBaseAction
from sekoiaio.utils import datetime_to_str


class AddIOCtoIOCCollectionAction(InThreatBaseAction):
    def perform_request(self, indicators, ioc_collection_id, indicator_type, valid_for):
        data = {"format": indicator_type, "indicators": "\n".join(indicators)}
        if valid_for:
            data["valid_until"] = datetime_to_str(datetime.now() + timedelta(days=valid_for))

        result = requests.post(
            self.url("ioc-collections/" + ioc_collection_id + "/indicators/text"), json=data, headers=self.headers
        )

        if not result.ok:
            self.error(
                f"Could not post indicators to IOC Collection: '{result.text}', status code: {result.status_code}"
            )

    def add_IP_action(self, indicators, ioc_collection_id, valid_for):
        ipv4 = []
        ipv6 = []
        for ip in indicators:
            try:
                ipaddress.IPv4Address(ip)
                ipv4.append(ip)
            except ValueError:
                pass

            try:
                ipaddress.IPv6Address(ip)
                ipv6.append(ip)
            except ValueError:
                pass

        if ipv4:
            self.perform_request(ipv4, ioc_collection_id, "ipv4-addr.value", valid_for)
        if ipv6:
            self.perform_request(ipv6, ioc_collection_id, "ipv6-addr.value", valid_for)

    def run(self, arguments: dict):
        indicator_type_mapping = {
            "domain": "domain-name.value",
            "url": "url.value",
            "email": "email-addr.value",
            "hash": "file.hashes",
        }

        indicators = self.json_argument("indicators", arguments)
        ioc_collection_id = arguments.get("ioc_collection_id")
        indicator_type = arguments.get("indicator_type")
        valid_for = int(arguments.get("valid_for", 0))

        if str(indicator_type) == "IP address":
            self.add_IP_action(indicators, ioc_collection_id, valid_for)
        else:
            if _type := indicator_type_mapping.get(str(indicator_type)):
                self.perform_request(indicators, ioc_collection_id, _type, valid_for)
            else:
                self.error(f"Improper indicator type {indicator_type}")
