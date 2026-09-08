import ipaddress
from datetime import datetime, timedelta

import requests
from pydantic import TypeAdapter, ValidationError

from sekoiaio.utils import datetime_to_str

from .base import InThreatBaseAction

IP_ADDRESS_ADAPTER: TypeAdapter[ipaddress.IPv4Address | ipaddress.IPv6Address] = TypeAdapter(
    ipaddress.IPv4Address | ipaddress.IPv6Address
)


class AddIOCtoIOCCollectionAction(InThreatBaseAction):
    def perform_request(self, indicators, ioc_collection_id, indicator_type, valid_for):
        """Post indicators to the IOC collection text endpoint."""
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

    def flatten_and_validate(self, indicators):
        """Flatten nested indicator containers into a flat string list."""
        if isinstance(indicators, list):
            result = []
            for indicator in indicators:
                result.extend(self.flatten_and_validate(indicator))
            return result

        return [str(indicators)]

    def add_IP_action(self, indicators, ioc_collection_id, valid_for):
        """Split IP indicators by version and submit them in dedicated requests.

        Valid anonymized examples: 198.51.100.10, 203.0.113.7, 2001:db8::1
        Rejected example (CIDR): 198.51.100.10/32
        """
        ipv4 = []
        ipv6 = []
        invalid_ips = []
        for ip in indicators:
            normalized_ip = str(ip).strip()
            if not normalized_ip:
                invalid_ips.append(str(ip))
                continue

            try:
                parsed_ip = IP_ADDRESS_ADAPTER.validate_python(normalized_ip)
                if isinstance(parsed_ip, ipaddress.IPv4Address):
                    ipv4.append(normalized_ip)
                else:
                    ipv6.append(normalized_ip)
            except ValidationError:
                invalid_ips.append(normalized_ip)

        if invalid_ips:
            raise ValueError(
                "Invalid IP indicator(s): "
                + ", ".join(invalid_ips)
                + ". Expected plain IPv4/IPv6 addresses (CIDR notation is not supported). "
                + "Examples: 198.51.100.10, 203.0.113.7, 2001:db8::1"
            )

        if not ipv4 and not ipv6:
            raise ValueError("No valid IP indicators were provided")

        if ipv4:
            self.perform_request(ipv4, ioc_collection_id, "ipv4-addr.value", valid_for)
        if ipv6:
            self.perform_request(ipv6, ioc_collection_id, "ipv6-addr.value", valid_for)

    def run(self, arguments: dict):
        """Resolve input indicators and dispatch the matching IOC creation flow."""
        indicator_type_mapping = {
            "domain": "domain-name.value",
            "url": "url.value",
            "email": "email-addr.value",
            "hash": "file.hashes",
        }

        indicators = self.json_argument("indicators", arguments, required=False)
        single_indicator = arguments.get("indicator")
        ioc_collection_id = arguments.get("ioc_collection_id")
        indicator_type = arguments.get("indicator_type")
        valid_for = int(arguments.get("valid_for", 0))

        indicators_was_provided = "indicators" in arguments
        single_indicator_was_provided = "indicator" in arguments and single_indicator is not None

        if indicators_was_provided:
            result_indicators = self.flatten_and_validate(indicators) if indicators is not None else []
        elif single_indicator_was_provided:
            result_indicators = [single_indicator]
        else:
            result_indicators = []

        if str(indicator_type) == "IP address":
            if not isinstance(indicators, list) and not single_indicator:
                raise ValueError("Indicators should be list type, or you should provide a single indicator value")

            self.add_IP_action(result_indicators, ioc_collection_id, valid_for)
        else:
            if _type := indicator_type_mapping.get(str(indicator_type)):
                self.perform_request(result_indicators, ioc_collection_id, _type, valid_for)
            else:
                self.error(f"Improper indicator type {indicator_type}")
