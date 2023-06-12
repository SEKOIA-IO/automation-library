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
