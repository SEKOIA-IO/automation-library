from .base import MicrosoftADAction
from pydantic import BaseModel
from typing import List


class SearchArguments(BaseModel):
    search_filter: str
    basedn: str
    attributes: List[str] | None


class SearchAction(MicrosoftADAction):
    name = "Search"
    description = "Search in your AD"

    def run(self, arguments: SearchArguments) -> dict:
        attributes = arguments.attributes or "ALL_ATTRIBUTES"
        try:
            self.client.search(
                search_base=arguments.basedn, search_filter=arguments.search_filter, attributes=attributes
            )
        except:
            raise Exception(f"Failed to search in this base {arguments.basedn}")

        return self.client.response
