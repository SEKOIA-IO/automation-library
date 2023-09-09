from typing import Any

from .base_get_event import BaseGetEvents


class GetEvents(BaseGetEvents):
    def run(self, arguments):
        self.configure_http_session()

        event_search_job_uuid: str = self.trigger_event_search_job(
            query=arguments["query"],
            earliest_time=arguments["earliest_time"],
            latest_time=arguments["latest_time"],
            limit=arguments.get("limit"),
        )

        self.wait_for_search_job_execution(event_search_job_uuid=event_search_job_uuid)

        results: list[dict[str, Any]] | None = None
        response_content: dict[str, Any] = {}
        limit: int = min(1000, arguments.get("limit")) if "limit" in arguments else 1000
        offset: int = 0

        while results is None or response_content["total"] > offset + limit:
            response_events = self.http_session.get(
                f"{self.events_api_path}/search/jobs/{event_search_job_uuid}/events",
                params={"limit": limit, "offset": offset},
            )
            response_events.raise_for_status()

            response_content = response_events.json()
            if results is None:
                results = []
            results += response_content["items"]

            offset += limit

        return {"events": results}
