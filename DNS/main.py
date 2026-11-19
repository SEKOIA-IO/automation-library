from sekoia_automation.module import Module

from dns_modules.action_dns_reverse_search import DnsReverseSearchAction


def main():
    module = Module()
    module.register(DnsReverseSearchAction, "action_dns_reverse_search")
    module.run()


def fission_main():
    main()
    return "ok"


if __name__ == "__main__":
    main()
