from sekoia_automation.module import Module

from binaryedges import (
    GetQueryCveIpTarget,
    GetQueryDataleaksEmailEmail,
    GetQueryDataleaksInfo,
    GetQueryDataleaksOrganizationDomain,
    GetQueryDomainsDnsTarget,
    GetQueryDomainsIpTarget,
    GetQueryDomainsSearch,
    GetQueryDomainsSubdomainTarget,
    GetQueryImageIpTarget,
    GetQueryImageSearch,
    GetQueryImageTags,
    GetQueryIpHistoricalTarget,
    GetQueryIpTarget,
    GetQueryScoreIpTarget,
    GetQuerySearch,
    GetQuerySearchStats,
    GetQuerySensorsIpTarget,
    GetQuerySensorsSearch,
    GetQuerySensorsSearchStats,
    GetQuerySensorsTagTag,
    GetQueryTorrentHistoricalTarget,
    GetQueryTorrentIpTarget,
    GetQueryTorrentSearch,
    GetQueryTorrentSearchStats,
    GetUserSubscription,
)

if __name__ == "__main__":
    module = Module()
    module.register(GetUserSubscription, "get-user/subscription")
    module.register(GetQueryIpTarget, "get-query/ip/{target}")
    module.register(GetQueryIpHistoricalTarget, "get-query/ip/historical/{target}")
    module.register(GetQuerySearch, "get-query/search")
    module.register(GetQuerySearchStats, "get-query/search/stats")
    module.register(GetQueryImageIpTarget, "get-query/image/ip/{target}")
    module.register(GetQueryImageSearch, "get-query/image/search")
    module.register(GetQueryImageTags, "get-query/image/tags")
    module.register(GetQueryTorrentIpTarget, "get-query/torrent/ip/{target}")
    module.register(GetQueryTorrentHistoricalTarget, "get-query/torrent/historical/{target}")
    module.register(GetQueryTorrentSearch, "get-query/torrent/search")
    module.register(GetQueryTorrentSearchStats, "get-query/torrent/search/stats")
    module.register(GetQueryDataleaksEmailEmail, "get-query/dataleaks/email/{email}")
    module.register(GetQueryDataleaksOrganizationDomain, "get-query/dataleaks/organization/{domain}")
    module.register(GetQueryDataleaksInfo, "get-query/dataleaks/info")
    module.register(GetQueryScoreIpTarget, "get-query/score/ip/{target}")
    module.register(GetQueryCveIpTarget, "get-query/cve/ip/{target}")
    module.register(GetQueryDomainsSubdomainTarget, "get-query/domains/subdomain/{target}")
    module.register(GetQueryDomainsDnsTarget, "get-query/domains/dns/{target}")
    module.register(GetQueryDomainsIpTarget, "get-query/domains/ip/{target}")
    module.register(GetQueryDomainsSearch, "get-query/domains/search")
    module.register(GetQuerySensorsIpTarget, "get-query/sensors/ip/{target}")
    module.register(GetQuerySensorsSearch, "get-query/sensors/search")
    module.register(GetQuerySensorsSearchStats, "get-query/sensors/search/stats")
    module.register(GetQuerySensorsTagTag, "get-query/sensors/tag/{tag}")
    module.run()
