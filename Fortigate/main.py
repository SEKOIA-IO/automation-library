# third parties
from sekoia_automation.module import Module

from fortigate.action_fortigate_add_fqdn import FortigateAddFQDNAction
from fortigate.action_fortigate_add_group_address import FortigateAddGroupAddress

# internals
from fortigate.action_fortigate_add_ip_address import FortigateAddIPAction

if __name__ == "__main__":
    module = Module()
    module.register(FortigateAddIPAction, "fortigate_add_ip_address")
    module.register(FortigateAddFQDNAction, "fortigate_add_fqdn")
    module.register(FortigateAddGroupAddress, "fortigate_add_group_address")
    module.run()
