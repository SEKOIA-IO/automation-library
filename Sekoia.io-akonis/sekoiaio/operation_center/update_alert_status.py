from posixpath import join as urljoin

from sekoia_automation.action import Action
import requests
from tenacity import retry, wait_exponential, stop_after_attempt


STATUS_UUIDS = {
    "PENDING": "2efc4930-1442-4abb-acf2-58ba219a4fd0",
    "ACKNOWLEDGED": "8f206505-af6d-433e-93f4-775d46dc7d0f",
    "ONGOING": "1f2f88d5-ff5b-48bf-bbbc-00c2fff82d9f",
    "REJECTED": "4f68da89-38e0-4703-a6ab-652f02bdf24e",
    "CLOSED": "1738b1c1-767d-489e-bada-19176621a007",
}
ACTION_UUIDS = [
    "937bdabf-6a08-434b-b6d3-d7447e4e452a",
    "c39a0a95-aa2c-4d0d-8d2e-d3decf426eea",
    "ade85d7b-7507-4026-bfc6-cc006d10ddac",
    "1390be4e-ced8-4dd6-9bed-573471b235ab",
]


class UpdateAlertStatus(Action):

    def url(self, alert_uuid: str) -> str:
        return urljoin(self.module.configuration["base_url"], f"api/v1/sic/alerts/{alert_uuid}/workflow")

    @property
    def headers(self) -> dict:
        api_key = self.module.configuration["api_key"]
        return {"Authorization": f"Bearer {api_key}"}

    @retry(
        reraise=True,
        wait=wait_exponential(max=300),
        stop=stop_after_attempt(10),
    )
    def perform_request(self, alert_uuid: str, status: str, comment: str | None = None):
        if status in STATUS_UUIDS.values() or status in ACTION_UUIDS:
            result = requests.patch(
                self.url(alert_uuid), headers=self.headers, json={"action_uuid": status, "comment": comment}
            )
        elif status.upper() in STATUS_UUIDS:
            result = requests.patch(
                self.url(alert_uuid),
                headers=self.headers,
                json={"action_uuid": STATUS_UUIDS[status.upper()], "comment": comment},
            )
        else:
            self.error(f"Invalid status: {status}")
            return
        if result.status_code >= 500:
            self.error(f"Could not change alert {alert_uuid} status, status code: {result.status_code}")
            result.raise_for_status()
        return result.json()

    def run(self, arguments: dict):
        status = arguments["status"]
        alert_uuid = arguments["uuid"]
        comment = arguments.get("comment")
        return self.perform_request(alert_uuid, status, comment)
