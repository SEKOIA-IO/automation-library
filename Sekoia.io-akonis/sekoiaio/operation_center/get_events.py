from typing import Any

from .base_get_event import BaseGetEvents


class GetEvents(BaseGetEvents):
    def run(self, arguments):
        limit = min(self.MAX_LIMIT, arguments.get("limit") or self.DEFAULT_LIMIT)
        self.configure_http_session()

        event_search_job_uuid: str = self.trigger_event_search_job(
            query=arguments["query"],
            earliest_time=arguments["earliest_time"],
            latest_time=arguments["latest_time"],
            limit=limit,
        )

        self.wait_for_search_job_execution(event_search_job_uuid=event_search_job_uuid)

        results: list[dict[str, Any]] = []
        offset: int = 0
        total: None | int = None

        while total is None or total > offset:
            response_events = self.http_session.get(
                f"{self.events_api_path}/search/jobs/{event_search_job_uuid}/events",
                params={"limit": limit, "offset": offset},
                timeout=20,
            )
            response_events.raise_for_status()

            response_content = response_events.json()
            if not response_content["items"]:
                num_results = len(results)
                if num_results < response_content["total"] and num_results < limit:
                    self.log(
                        "Number of fetched results doesn't match total",
                        level="error",
                        num_results=num_results,
                        total=response_content["total"],
                        search_job=event_search_job_uuid,
                    )
                break
            results += response_content["items"]
            total = min(response_content["total"], limit)

            offset += limit

        return {"events": results}
