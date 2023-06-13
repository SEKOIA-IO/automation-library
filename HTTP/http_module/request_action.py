import requests
from sekoia_automation.action import Action
from tenacity import Retrying, stop_after_attempt, wait_exponential


class RequestAction(Action):
    """
    Action to request an HTTP resource
    """

    def _retry(self):
        return Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    def run(self, arguments) -> dict:
        method = arguments.get("method")
        data = arguments.get("data")
        json = arguments.get("json")
        params = arguments.get("params")
        url = arguments.get("url")
        headers = arguments.get("headers")
        fail_on_http_error = arguments.get("fail_on_http_error", True)

        self.log(message=f"Request URL module started. Target URL: {url}", level="info")

        for attempt in self._retry():
            with attempt:
                response = requests.request(
                    method=method,
                    url=url,
                    data=data,
                    json=json,
                    params=params,
                    headers=headers,
                )

        if fail_on_http_error and not response.ok:
            # Will end action as in error
            self.error(f"HTTP Request failed: {url} with {response.status_code}")

        json_response = None
        if "application/json" in response.headers.get("Content-Type", "").lower():
            json_response = response.json()

        return {
            "reason": response.reason,
            "status_code": response.status_code,
            "url": response.url,
            "headers": dict(response.headers),
            "encoding": response.encoding,
            "elapsed": response.elapsed.total_seconds(),
            "text": response.text,
            "json": json_response,
        }
