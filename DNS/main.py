from sekoia_automation.module import Module
from dns_modules.action_dns_reverse_search import DnsReverseSearchAction

if __name__ == "__main__":
    module = Module()
    module.register_action("action_dns_reverse_search", DnsReverseSearchAction)
    module.run()
