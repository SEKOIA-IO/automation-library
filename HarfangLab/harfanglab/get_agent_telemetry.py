# coding: utf-8

# natives
from typing import Any
from datetime import datetime, timedelta

import requests
from sekoia_automation.action import Action


class GetAgentTelemetry(Action):
    """
    Action to retrieve telemetry for a specific HarfangLab agent
    """

    def send_request(self, base_url, api_endpoint, api_token, params):
        url = base_url.rstrip("/") + api_endpoint
        resp = requests.get(
            url,
            headers={"Authorization": f"Token {api_token}"},
            params=params,
        )
        resp.raise_for_status()
        return resp

    def run(self, arguments) -> list[dict]:

        telemetry_urls = {
            "processes": "/api/data/telemetry/Processes/",
            "binary": "/api/data/telemetry/Binary/",
            "network": "/api/data/telemetry/Network/",
            "eventlog": "/api/data/telemetry/FullEventLog/",
            "dns": "/api/data/telemetry/DNSResolution/",
            "windows_authentications": "/api/data/telemetry/authentication/AuthenticationWindows/",
            "linux_authentications": "/api/data/telemetry/authentication/AuthenticationLinux/",
            "macos_authentications": "/api/data/telemetry/authentication/AuthenticationMacos/",
        }

        agent_id = arguments.get("agent_id", "")
        event_types = arguments.get(
            "event_types", ["processes", "windows_authentications", "linux_authentications", "macos_authentications"]
        )
        alert_created = arguments.get("alert_created", "")
        timerange = arguments.get("timerange", 15)
        dt = datetime.fromisoformat(alert_created.replace("Z", "+00:00"))
        start = (dt - timedelta(minutes=timerange)).isoformat().replace("+00:00", "Z")
        end = (dt + timedelta(minutes=timerange)).isoformat().replace("+00:00", "Z")
        instance_url: str = self.module.configuration["url"]
        api_token: str = self.module.configuration["api_token"]

        results = []
        for event_type in event_types:
            offset = 0
            if event_type not in telemetry_urls.keys():
                raise ValueError(f"Invalid event type: {event_type}. Must be one of {list(telemetry_urls.keys())}.")
            while True:
                resp = self.send_request(
                    base_url=instance_url,
                    api_endpoint=telemetry_urls[event_type],
                    api_token=api_token,
                    params={
                        "agent.agentid": agent_id,
                        "@event_create_date__gte": start,
                        "@event_create_date__lte": end,
                        "limit": 50,
                        "offset": offset,
                    },
                )
                js = resp.json()
                next_query = js["next"]
                for r in js["results"]:
                    results.append(r)
                if next_query is None:
                    break
                offset += len(js["results"])

        return results
