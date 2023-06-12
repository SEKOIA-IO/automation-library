from sekoia_automation.module import Module

from whois_module.whois_action import WhoisAction

if __name__ == "__main__":
    module = Module()

    module.register(WhoisAction, "whois")
    module.run()
