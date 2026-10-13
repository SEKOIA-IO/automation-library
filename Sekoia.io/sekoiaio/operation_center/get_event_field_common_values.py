from .base_get_event import BaseGetEvents


class GetEventFieldCommonValues(BaseGetEvents):
    def run(self, arguments):
        self.configure_http_session()

        event_search_job_uuid = self.trigger_event_search_job(
            query=arguments["query"],
            earliest_time=arguments["earliest_time"],
            latest_time=arguments["latest_time"],
            limit=min(self.MAX_LIMIT, arguments.get("limit") or self.DEFAULT_LIMIT),
        )

        self.wait_for_search_job_execution(event_search_job_uuid=event_search_job_uuid)

        # Retrieve the fields values
        results = {}
        must_continue_in_pages = True
        limit = 1000
        offset = 0

        requested_fields = {field.strip() for field in arguments["fields"].split(",") if field.strip()}

        while must_continue_in_pages:
            must_continue_in_pages = False

            response_fields = self.http_session.get(
                f"{self.events_api_path}/search/jobs/{event_search_job_uuid}/fields",
                params={"limit": limit, "offset": offset},
                timeout=20,
            )
            response_fields.raise_for_status()

            response_content = response_fields.json()
            items = response_content.get("items", [])
            for item in items:
                offset += 1
                if item["name"] in requested_fields:
                    results[item["name"]] = item["most_common_values"]

            # Fetch the next page while some requested fields are missing; stop on an empty page
            if items and offset < response_content["total"] and len(results) < len(requested_fields):
                must_continue_in_pages = True

        return {
            "fields": [
                {"name": field_name, "common_values": field_values} for field_name, field_values in results.items()
            ]
        }
