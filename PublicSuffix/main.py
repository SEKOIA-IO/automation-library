from sekoia_automation.module import Module

from public_suffix.get_private_domains_action import GetPrivateDomainsAction

if __name__ == "__main__":
    module = Module()

    module.register(GetPrivateDomainsAction, "get-private-domains")

    module.run()
