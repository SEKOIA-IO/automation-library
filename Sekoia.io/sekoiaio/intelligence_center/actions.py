"""
Module for actions that are not fully generic
"""


from sekoia_automation.action import GenericAPIAction

from sekoiaio.intelligence_center import base_url


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
    verb= "post"
    endpoint= base_url + "objects/search?limit=10",
    query_parameters= ["term", "sort"],

    def run(self, arguments) -> dict:
        results = super().run(arguments)

        if results.get("external_references")[0].get("source_name").startswith("FLINT"):
            url = "https://app.sekoia.io/intelligence/objects/"+ results.get("id", "")
            results["external_references"][0]["url"] = url
        
        return results