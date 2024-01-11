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
                continue

            try:
                ipaddress.IPv6Address(ip)
                ipv6.append(ip)
            except ValueError:
                continue

        if ipv4:
            self.perform_request(self, ipv4, ioc_collection_id, "ipv4-addr.value", valid_for)
        if ipv6:
            self.perform_request(self, ipv6, ioc_collection_id, "ipv4-addr.value", valid_for)

    def run(self, arguments: dict):
        indicator_type_mapping = {
            "domain": "domain-name.value",
            "url": "url.value",
            "email": "email-addr.value",
            "hash": "file.hashes",
        }

        indicators = self.json_argument("indicators", arguments)
        ioc_collection_id = self.json_argument("ioc_collection_id", arguments)
        indicator_type = self.json_argument("indicator_type", arguments)
        valid_for = self.json_argument("valid_for", arguments)

        if indicator_type == "IP":
            self.add_IP_action(self, indicators, ioc_collection_id, valid_for)
        else:
            self.perform_request(
                self, indicators, ioc_collection_id, indicator_type_mapping["indicator_type"], valid_for
            )
