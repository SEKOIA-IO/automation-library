import json
from posixpath import join as urljoin

from sekoia_automation.action import Action
from websocket._core import create_connection


class GetAggregationQuery(Action):
    def run(self, arguments: dict):
        api_key = self.module.configuration["api_key"]
        base_url = self.module.configuration["base_url"]
        ws_base_url = "wss://" + base_url.split("//")[1]

        query = {
            "aggregation": arguments["aggregation_type"],
            "field": arguments.get("aggregation_field"),
            "term": arguments.get("query_term", ""),
            "filters": arguments.get("filters", []),
            "range": [arguments["earliest_time"], arguments["latest_time"]],
            "minutes_per_bucket": arguments["minutes_per_bucket"],
        }
        ws = create_connection(
            urljoin(ws_base_url, "api/v1/events/stats"),
            header={"Authorization": f"Bearer {api_key}"},
        )
        ws.send(json.dumps(query))
        result = ws.recv()
        ws.close()
        return json.loads(result)
