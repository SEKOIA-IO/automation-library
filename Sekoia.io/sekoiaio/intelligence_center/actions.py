"""
Module for actions that are not fully generic
"""


from sekoia_automation.action import GenericAPIAction

from sekoiaio.intelligence_center import base_url
import re
from posixpath import join as urljoin


class PostBundleAction(GenericAPIAction):
    verb = "post"
    endpoint = base_url + "bundles"
    query_parameters = ["auto_merge", "name", "enrich", "assigned_to"]

    def get_body(self, arguments):
        return {"data": self.json_argument("bundle", arguments)}

    def run(self, arguments) -> dict | None:
        if results := super().run(arguments):
            return results.get("data")

        return None


class GetContextAction(GenericAPIAction):
    verb = "post"
    endpoint = base_url + "objects/search"
    query_parameters = ["term", "sort"]

    def run(self, arguments) -> dict:
        results = super().run(arguments)
        items = results.get("items")

        for item in items:
            if item.get("external_references"):
                external_references = item.get("external_references")
                # Search for FLINT source_name and add url to them
                if external_references[0].get("source_name").startswith("FLINT"):
                    ind = items.index(item)
                    url = "https://app.sekoia.io/intelligence/objects/" + item.get("id")
                    item["external_references"][0].update({"url": url})
                    items[ind] = item

        return {"items": items, "has_more": results.get("has_more")}
