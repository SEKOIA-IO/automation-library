from action_base import SophosEDRAction


class ActionSophosEDRIsolateEndpoint(SophosEDRAction):
    def run(self, arguments: dict) -> dict:
        endpoints_ids = arguments["endpoints_ids"]
        comment = arguments.get("comment")

        data = {"enabled": True, "ids": endpoints_ids}
        if comment:
            data["comment"] = comment

        return self.call_endpoint(method="post", url="endpoint/v1/endpoints/isolation", data=data)
