from censys.base import CensysIndex

from censys_module.base import CensysAction


class ReportAction(CensysAction):
    DEFAULT_BUCKETS = 50
    MAX_BUCKETS = 500

    def get_buckets_number(self, arguments: dict) -> int:
        try:
            buckets = int(arguments.get("buckets", self.DEFAULT_BUCKETS))
            return min(buckets, self.MAX_BUCKETS)
        except (KeyError, ValueError):
            return self.DEFAULT_BUCKETS

    def execute_request(self, index_class: CensysIndex, arguments: dict):
        return index_class.report(
            query=arguments["query"],
            field=arguments["field"],
            buckets=self.get_buckets_number(arguments),
        )
