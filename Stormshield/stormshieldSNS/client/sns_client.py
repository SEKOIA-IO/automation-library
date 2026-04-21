from ipaddress import ip_address

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class StormshieldSNSClient:
    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

    def block_ip(self, ip: str, duration_s: int = 3600) -> dict:
        validated_ip = str(ip_address(ip))

        endpoint = f"{self.base_url}/papi/v1/banned-ip-list/addresses/{validated_ip}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"duration_s": duration_s}

        response = requests.request(
            method="PUT",
            url=endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout,
            verify=False,
        )

        body = self._parse_response_body(response)

        if not response.ok:
            raise RuntimeError(f"Failed to block IP {validated_ip}: HTTP {response.status_code} - {body}")

        return {
            "status": "success",
            "ip_address": validated_ip,
            "duration_s": duration_s,
            "message": body.get("result", {}).get("message", "IP blocked successfully"),
            "response": body,
        }

    @staticmethod
    def _parse_response_body(response: requests.Response) -> dict | str:
        try:
            return response.json()
        except ValueError:
            return response.text
