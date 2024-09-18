from collections import defaultdict
import pandas as pd

from management.mgmtsdk_v2_1.services.threat_intelligence import IocQueryFilter
from pydantic import BaseModel

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.filters import BaseFilters
from sentinelone_module.helpers import stix_to_indicators


class CreateIOCsFilters(BaseFilters):
    account_ids: list[str] | None
    group_ids: list[str] | None
    site_ids: list[str] | None

    class Config:
        query_filter_class = IocQueryFilter


class CreateIOCsArguments(BaseModel):
    filters: CreateIOCsFilters | None
    sekoia_base_url: str | None
    stix_objects_path: str

    def get_query_filters(self):
        if self.filters is None:
            return None
        return self.filters.to_query_filter()


class CreateIOCsAction(SentinelOneAction):
    name = "Create IOCs"
    description = "Create and push IOCs to SentinelOne"

    DEFAULT_SEKOIA_BASE_URL = "https://app.sekoia.io"
    SUPPORTED_TYPES_MAP = {
        "ipv4-addr": {"value": "IPV4"},
        "ipv6-addr": {"value": "IPV6"},
        "domain-name": {"value": "DNS"},
        "file": {"hashes.MD5": "MD5", "hashes.SHA1": "SHA1", "hashes.sha256": "SHA256"},
        "url": {"value": "URL"},
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.sekoia_base_url = self.DEFAULT_SEKOIA_BASE_URL

    def get_payload(self, value, type):
        return {
            "value": value,
            "type": type,
            "source": "Sekoia.io",
        }

    def get_valid_indicators(self, stix_objects):
        seen_values = defaultdict(list)
        results = {"valid": []}
        for object in stix_objects:
            # Extract value and type from pattern
            self.log(message=f"Object in stix_objects {str(object)}", level="debug")
            indicators = stix_to_indicators(stix_object=object, supported_types_map=self.SUPPORTED_TYPES_MAP)
            for indicator in indicators:
                ioc_value = indicator["value"]
                ioc_type = indicator["type"]
                result = self.get_payload(value=ioc_value, type=ioc_type)

                # Handle revoked objects
                if object.get("revoked", False):
                    continue

                # Ignore this IOC if the same value has already been processed
                if ioc_value in seen_values[ioc_type]:
                    continue

                # Add expiration and creation data if exists
                valid_until = object.get("valid_until")
                created_time = object.get("created")
                if valid_until:
                    result["validUntil"] = valid_until
                if created_time:
                    result["createdTime"] = created_time

                seen_values[ioc_type].append(ioc_value)
                results["valid"].append(result)

        return results

    def run(self, arguments: CreateIOCsArguments):
        if arguments.sekoia_base_url:
            self.sekoia_base_url = arguments.sekoia_base_url

        self.log("Starting looking for stix_objects in the provided path")
        stix_objects = self.json_argument("stix_objects", arguments.model_dump())

        if not stix_objects:
            self.log("Empty or missing STIX objects received from the data source.")

        self.log("Start getting valid indicators")
        indicators = self.get_valid_indicators(stix_objects)
        if len(indicators["valid"]) == 0:
            self.log("Received indicators were not valid and/or not supported")
            return
        df_indicators = pd.DataFrame(indicators["valid"])

        self.log("Start sending indicators to SentinelOne !!")
        response = self.client.threat_intel.create_or_update_ioc(
            df_indicators, query_filter=arguments.get_query_filters()
        )

        # Return the response as a list of JSON objects
        final_response = [item.to_json() for item in response]

        return final_response
