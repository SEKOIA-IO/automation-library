from sekoia_automation.module import Module
from reversedns_modules.action_reverse_dns import ReverseDnsAction

if __name__ == "__main__":
    module = Module()
    module.register(ReverseDnsAction, "reversedns_lookup")
    module.run()
