from sekoia_automation.action import GenericAPIAction


class BinaryEdgesAction(GenericAPIAction):
    def get_headers(self):
        headers = {"Accept": "application/json"}
        api_key = self.module.configuration.get("api_key")
        if api_key:
            headers["X-Key"] = api_key
        return headers


base_url = ""

GetUserSubscription = type(
    "GetUserSubscription",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "user/subscription",
        "query_parameters": [],
    },
)

GetQueryIpTarget = type(
    "GetQueryIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/ip/{target}",
        "query_parameters": [],
    },
)

GetQueryIpHistoricalTarget = type(
    "GetQueryIpHistoricalTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/ip/historical/{target}",
        "query_parameters": [],
    },
)

GetQuerySearch = type(
    "GetQuerySearch",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/search",
        "query_parameters": ["query", "page", "only_ips"],
    },
)

GetQuerySearchStats = type(
    "GetQuerySearchStats",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/search/stats",
        "query_parameters": ["query", "type", "order"],
    },
)

GetQueryImageIpTarget = type(
    "GetQueryImageIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/image/ip/{target}",
        "query_parameters": ["page"],
    },
)

GetQueryImageSearch = type(
    "GetQueryImageSearch",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/image/search",
        "query_parameters": ["query", "page"],
    },
)

GetQueryImageTags = type(
    "GetQueryImageTags",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/image/tags",
        "query_parameters": [],
    },
)

GetQueryTorrentIpTarget = type(
    "GetQueryTorrentIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/torrent/ip/{target}",
        "query_parameters": [],
    },
)

GetQueryTorrentHistoricalTarget = type(
    "GetQueryTorrentHistoricalTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/torrent/historical/{target}",
        "query_parameters": [],
    },
)

GetQueryTorrentSearch = type(
    "GetQueryTorrentSearch",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/torrent/search",
        "query_parameters": ["query", "page"],
    },
)

GetQueryTorrentSearchStats = type(
    "GetQueryTorrentSearchStats",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/torrent/search/stats",
        "query_parameters": ["query", "type", "days", "order"],
    },
)

GetQueryDataleaksEmailEmail = type(
    "GetQueryDataleaksEmailEmail",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/dataleaks/email/{email}",
        "query_parameters": [],
    },
)

GetQueryDataleaksOrganizationDomain = type(
    "GetQueryDataleaksOrganizationDomain",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/dataleaks/organization/{domain}",
        "query_parameters": [],
    },
)

GetQueryDataleaksInfo = type(
    "GetQueryDataleaksInfo",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/dataleaks/info",
        "query_parameters": [],
    },
)

GetQueryScoreIpTarget = type(
    "GetQueryScoreIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/score/ip/{target}",
        "query_parameters": [],
    },
)

GetQueryCveIpTarget = type(
    "GetQueryCveIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/cve/ip/{target}",
        "query_parameters": [],
    },
)

GetQueryDomainsSubdomainTarget = type(
    "GetQueryDomainsSubdomainTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/domains/subdomain/{target}",
        "query_parameters": ["page"],
    },
)

GetQueryDomainsDnsTarget = type(
    "GetQueryDomainsDnsTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/domains/dns/{target}",
        "query_parameters": ["page"],
    },
)

GetQueryDomainsIpTarget = type(
    "GetQueryDomainsIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/domains/ip/{target}",
        "query_parameters": ["page"],
    },
)

GetQueryDomainsSearch = type(
    "GetQueryDomainsSearch",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/domains/search",
        "query_parameters": ["query", "page"],
    },
)

GetQuerySensorsIpTarget = type(
    "GetQuerySensorsIpTarget",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/sensors/ip/{target}",
        "query_parameters": [],
    },
)

GetQuerySensorsSearch = type(
    "GetQuerySensorsSearch",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/sensors/search",
        "query_parameters": ["query", "days", "page", "only_ips"],
    },
)

GetQuerySensorsSearchStats = type(
    "GetQuerySensorsSearchStats",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/sensors/search/stats",
        "query_parameters": ["query", "type", "days", "order"],
    },
)

GetQuerySensorsTagTag = type(
    "GetQuerySensorsTagTag",
    (BinaryEdgesAction,),
    {
        "verb": "get",
        "endpoint": base_url + "query/sensors/tag/{tag}",
        "query_parameters": ["days"],
    },
)
