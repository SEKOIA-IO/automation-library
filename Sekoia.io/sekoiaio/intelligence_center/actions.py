"""
Module for actions that are not fully generic
"""

from sekoia_automation.action import GenericAPIAction

from sekoiaio.intelligence_center import base_url


class EmptyBundleError(Exception):
    pass


class PostBundleAction(GenericAPIAction):
    verb = "post"
    endpoint = base_url + "bundles"
    query_parameters = ["auto_merge", "name", "enrich", "assigned_to"]

    def get_body(self, arguments):
        data = self.json_argument("bundle", arguments)
        if not data.get("objects"):
            raise EmptyBundleError("No objects in bundle")
        return {"data": self.json_argument("bundle", arguments)}

    def run(self, arguments) -> dict | None:
        try:
            if results := super().run(arguments):
                return results.get("data")
        except EmptyBundleError:
            pass

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
                for reference in external_references:
                    if reference.get("source_name").startswith("FLINT"):
                        index_item = items.index(item)
                        index_ref = external_references.index(reference)
                        url = "https://app.sekoia.io/intelligence/objects/" + item.get("id")
                        item["external_references"][index_ref].update({"url": url})
                        items[index_item] = item

        return {"items": items, "has_more": results.get("has_more")}
