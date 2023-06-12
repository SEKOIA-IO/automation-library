import time

from sekoia_automation.action import GenericAPIAction

from shodan.helpers import sanitize_node


class ShodanAPIAction(GenericAPIAction):
    query_parameters: list[str]

    def run(self, arguments) -> dict | None:
        result = super().run(arguments)
        return sanitize_node(result)

    def get_url(self, arguments):
        """Forge URL and add the api key for authentication in the query."""
        path = super().get_url(arguments)
        api_key = self.module.configuration.get("api_key")
        if "?" in path:
            path = f"{path}&key={api_key}"
        else:
            path = f"{path}?key={api_key}"
        return path

    def get_headers(self):
        """Simplified method."""
        return {"Accept": "application/json"}


base_url = ""


class GetShodanHost(ShodanAPIAction):
    verb = "get"
    endpoint = base_url + "shodan/host/{ip}"
    query_parameters: list[str] = ["history", "minify"]


class GetShodanHostCount(ShodanAPIAction):
    verb = "get"
    endpoint = base_url + "shodan/host/count"
    query_parameters: list[str] = ["query", "facets"]


class GetShodanHostSearch(ShodanAPIAction):
    verb = "get"
    endpoint = base_url + "shodan/host/search"
    query_parameters: list[str] = ["query", "facets", "minify"]

    _url = None

    def run(self, arguments) -> dict | None:
        """Allow multiples requests to get all pages in once."""
        max_pages = arguments.pop("max_pages", 1)
        result = None
        for page in range(1, max_pages + 1):
            arguments["page"] = page
            page_result = super().run(arguments)

            if page_result is None:
                return None  # the request failed, so the node run is in error and the playbook stops

            if not result:
                result = page_result
            else:
                result["matches"].extend(page_result["matches"])

            if page_result["total"] / 100 <= page:
                break

            time.sleep(1)  # Shodan API endpoints are rate-limited to 1 request/ second.

        return result

    def get_url(self, arguments):
        """Add the automatic pagination argument, and implement a cache mechanism."""
        # cache mechanism to not rebuild the url for each pagination call
        page = arguments.pop("page")
        if not self._url:
            self._url = super().get_url(arguments)
        return f"{self._url}&page={page}"


class GetDNSDomain(ShodanAPIAction):
    verb = "get"
    endpoint = base_url + "dns/domain/{domain}"
    query_parameters: list[str] = []


class GetDNSResolve(ShodanAPIAction):
    verb = "get"
    endpoint = base_url + "dns/resolve"
    query_parameters: list[str] = []

    def get_url(self, arguments):
        """Adds concatenated hostnames arguments to path."""
        path = super().get_url(arguments)
        return f'{path}&hostnames={",".join(arguments.pop("hostnames"))}'


class GetDNSReverse(ShodanAPIAction):
    verb = "get"
    endpoint = base_url + "dns/reverse"
    query_parameters: list[str] = []

    def get_url(self, arguments):
        """Adds concatenated ips arguments to path."""
        path = super().get_url(arguments)
        return f'{path}&ips={",".join(arguments.pop("ips"))}'
