import time
from datetime import datetime, timezone

import requests as requests
from requests import Response
from requests.auth import HTTPBasicAuth
from sekoia_automation.trigger import Trigger

# A triage item is an alert or an incident
TriageItemList = list[dict]
EventList = list[dict]


class SearchLightTrigger(Trigger):
    """
    This trigger reads the alerts & incidents raised in Digital Shadows SearchLight.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pagination_event_num_after: int = 0
        self.pagination_limit: int = 1000
        self.previous_alerts: list[dict] = []
        self.trigger_activation = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def run(self) -> None:  # pragma: no cover
        self.log(message="Digital Shadows SearchLight Trigger has started.", level="info")
        while True:
            try:
                new_alerts = self._fetch_alerts()
                if new_alerts:
                    self.log(
                        message=f"Sending a batch of {len(new_alerts)} alert messages",
                        level="info",
                    )
                    self.send_event(
                        event_name="DigitalShadows-SearchLight-alerts",
                        event={"alerts": new_alerts},
                    )
            except Exception as ex:
                self.log_exception(ex, message="An unknown exception occurred")
                raise

            time.sleep(self.configuration["frequency"])

    def save_last_event_num(self, triage_items_events: list[dict]) -> None:
        # Save last event number for pagination purpose
        for event in triage_items_events:
            if event["event-num"] > self.pagination_event_num_after:
                self.pagination_event_num_after = event["event-num"]

    def filter_event_type_create(self, triage_items_events: list[dict]) -> set:
        # Return UUIDs of events of type create
        event_type_create = [event for event in triage_items_events if "create" in event["event-action"]]
        return set(map(lambda event: event["triage-item-id"], event_type_create))

    def filter_triage_items(self, triage_items: list[dict]) -> tuple[set, set]:
        # Extract IDs of alerts and incidents from triage_items api response
        if not triage_items:
            return set(), set()

        alerts_uuids: set = {item["source"]["alert-id"] for item in triage_items if item["source"]["alert-id"]}
        incident_uuids: set = {item["source"]["incident-id"] for item in triage_items if item["source"]["incident-id"]}
        return alerts_uuids, incident_uuids

    def _query_api(
        self,
        endpoint: str,
        params: dict,
    ) -> EventList:
        """
        Query SearchLight API with configured credentials'
        pagination_event_num_after is an offset
        """
        headers: dict[str, str] = {"searchlight-account-id": self.module.configuration["searchlight_account_id"]}
        credentials: HTTPBasicAuth = HTTPBasicAuth(
            self.module.configuration["basicauth_key"],
            self.module.configuration["basicauth_secret"],
        )

        url: str = f"{self.module.configuration['api_url']}{endpoint}"

        response: Response = requests.get(
            url=url,
            auth=credentials,
            params=params,
            headers=headers,
        )
        response_body = response.json()
        if not response.ok:
            self.log(
                message=(
                    f"Request on SearchLight API to fetch {response.url} "
                    f"failed with status {response.status_code} - {response_body.get('message', '')}"
                ),
                level="error",
            )

            return []
        else:
            self.log(
                message="Successfully requested latest SearchLight events from API.",
                level="info",
            )
            return response_body

    def query_triage_items_events(self, pagination_limit: int | None = None) -> EventList:
        params = {
            "limit": pagination_limit or self.pagination_limit,
            "event-created-after": self.trigger_activation,
            "event-num-after": self.pagination_event_num_after,
        }
        return self._query_api(endpoint="/triage-item-events", params=params)

    def query_api(self, endpoint: str, uuids: set, pagination_limit: int | None = None) -> EventList:
        if len(uuids) == 0:
            return []

        return self._query_api(
            endpoint=endpoint,
            params={"id": uuids, "limit": pagination_limit or self.pagination_limit},
        )

    def _fetch_alerts(self) -> TriageItemList:
        """
        Pull alerts & incidents from API and return new items.
        """
        triage_item_events = self.query_triage_items_events()
        triage_item_events_uuids = self.filter_event_type_create(triage_item_events)

        self.save_last_event_num(triage_item_events)

        triage_items = self.query_api(endpoint="/triage-items", uuids=triage_item_events_uuids)
        alerts_uuids, incidents_uuids = self.filter_triage_items(triage_items)

        if not alerts_uuids and not incidents_uuids:
            return []

        alerts: list[dict] = self.query_api(endpoint="/alerts", uuids=alerts_uuids, pagination_limit=100)
        incidents: list[dict] = self.query_api(endpoint="/incidents", uuids=incidents_uuids, pagination_limit=100)

        return alerts + incidents
