# coding: utf-8

# natives
from typing import Any

import requests
from sekoia_automation.action import Action

# third parties
from harfanglab.models import HostnameEntry, HostnamesResult


class GetHostnamesByIP(Action):
    """
    Action to analyze a HarfangLab job that lists the process
    """

    def run(self, arguments) -> dict:
        target_ip = arguments.get("target_ip", "")
        get_only_last_seen = arguments.get("get_only_last_seen", False)

        instance_url: str = self.module.configuration["url"]
        api_token: str = self.module.configuration["api_token"]

        job_url = f"{instance_url}/api/data/endpoint/Agent/"
        params: dict = {"ipaddress": target_ip}

        response = requests.get(url=job_url, params=params, headers={"Authorization": f"Token {api_token}"})
        response.raise_for_status()

        data = response.json()

        # Check if data is a dictionary with a key "results" or directly a list
        result = data.get("results") if isinstance(data, dict) else data

        hostnames = [HostnameEntry(**entry) for entry in result]  # type: ignore
        if get_only_last_seen:
            most_recent_hostname = max(hostnames, key=lambda x: x.lastseen)
            hostnames_result = HostnamesResult(hostnames=[most_recent_hostname])
        else:
            hostnames_result = HostnamesResult(hostnames=hostnames)

        return hostnames_result.dict()
