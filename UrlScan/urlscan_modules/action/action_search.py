from typing import Any

from urlscan import Client

from urlscan_modules.base import ActionError, UrlScanAction
from urlscan_modules.formatters import build_indicator_query, build_search_results
from urlscan_modules.models import SearchArguments


class Search(UrlScanAction):
    def perform(self, client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
        args = SearchArguments.model_validate(arguments)
        indicator, query, size = args.indicator or "", args.query or "", args.size
        if bool(indicator) == bool(query):
            raise ActionError('Provide exactly one of "indicator" or "query"')

        q = query or build_indicator_query(indicator)
        params: dict[str, Any] = {"q": q, "size": size}
        if search_after := args.search_after:
            params["search_after"] = search_after

        response = self.call(client.get_json, "/api/v1/search/", params=params)
        return build_search_results(response, q, size, self.base_url)
