from typing import Any

from .base_get_event import BaseGetEvents


class GetEvents(BaseGetEvents):
    SEARCH_JOB_LIMIT = 5000

    def run(self, arguments):
        action_limit = arguments.get("limit")
        self.configure_http_session()

        event_search_job_uuid: str = self.trigger_event_search_job(
            query=arguments["query"],
            earliest_time=arguments["earliest_time"],
            latest_time=arguments["latest_time"],
            limit=action_limit,
        )

        self.wait_for_search_job_execution(event_search_job_uuid=event_search_job_uuid)

        results: list[dict[str, Any]] = []
        limit: int = min(1000, action_limit) if "limit" in arguments else 1000
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
                max_possible_results = (
                    min(self.SEARCH_JOB_LIMIT, action_limit) if action_limit else self.SEARCH_JOB_LIMIT
                )
                num_results = len(results)
                if num_results < response_content["total"] and num_results < max_possible_results:
                    self.log(
                        "Number of fetched results doesn't match total",
                        level="error",
                        num_results=num_results,
                        total=response_content["total"],
                        search_job=event_search_job_uuid,
                    )
                break
            results += response_content["items"]
            total = min(response_content["total"], action_limit) if action_limit else response_content["total"]

            offset += limit

        return {"events": results}
