from sekoia_automation.module import Module

from shodan import (
    GetDNSDomain,
    GetDNSResolve,
    GetDNSReverse,
    GetShodanHost,
    GetShodanHostCount,
    GetShodanHostSearch,
    AccountValidation,
)

if __name__ == "__main__":
    module = Module()

    module.register(GetShodanHost, "get-shodan/host/{ip}")
    module.register(GetShodanHostCount, "get-shodan/host/count")
    module.register(GetShodanHostSearch, "get-shodan/host/search")
    module.register(GetDNSDomain, "get-dns/domain/{domain}")
    module.register(GetDNSResolve, "get-dns/resolve")
    module.register(GetDNSReverse, "get-dns/reverse")
    module.register_account_validator(AccountValidation)

    module.run()
