from censys.base import CensysIndex

from censys_module.base import CensysAction


class SearchAction(CensysAction):
    def get_updated_at_field(self, arguments):
        return {
            "ipv4": "updated_at",
            "websites": "updated_at",
            "certificates": "metadata.updated_at",
        }[arguments["index"]]

    def get_query(self, arguments: dict) -> str:
        if not arguments.get("last_run"):
            return arguments["query"]
        updated_at_field = self.get_updated_at_field(arguments)
        return f"({arguments['query']}) AND {updated_at_field}: [{arguments['last_run']} TO *]"

    def get_max_records(self, arguments: dict):
        try:
            max_requests = int(arguments.get("max_requests", 1))
        except ValueError:
            max_requests = 1
        if max_requests < 1:
            return None
        return max_requests * 100

    def execute_request(self, index_class: CensysIndex, arguments: dict):
        return list(
            index_class.search(
                query=self.get_query(arguments),
                fields=arguments.get("fields"),
                max_records=self.get_max_records(arguments),
            )
        )
