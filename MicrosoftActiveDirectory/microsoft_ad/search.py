from .base import MicrosoftADAction
from pydantic import BaseModel
from typing import List
from ldap3 import ALL_ATTRIBUTES


class SearchArguments(BaseModel):
    search_filter: str
    basedn: str
    attributes: List[str] | None


class SearchAction(MicrosoftADAction):
    name = "Search"
    description = "Search in your AD"

    def make_serializable(self, data):
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.hex()
        elif isinstance(data, (list, tuple)):
            return [self.make_serializable(item) for item in data]
        elif hasattr(data, "entry_to_json"):
            return data.entry_to_json()
        elif isinstance(data, dict):
            return {key: self.make_serializable(value) for key, value in data.items()}
        else:
            return data

    def transform_ldap_results(self, entries):
        transformed = []
        for entry in entries:
            if "attributes" in entry:
                serialized_entry = self.make_serializable(entry["attributes"])
                transformed.append(serialized_entry)
        return transformed

    def run(self, arguments: SearchArguments) -> dict:
        attributes = arguments.attributes or ALL_ATTRIBUTES
        try:
            self.client.search(
                search_base=arguments.basedn, search_filter=arguments.search_filter, attributes=attributes
            )
        except:
            raise Exception(f"Failed to search in this base {arguments.basedn}")

        return {"search_result": self.transform_ldap_results(self.client.response)}
