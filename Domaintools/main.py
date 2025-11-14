from sekoia_automation.module import Module

from domaintools.get_domain_reputation import DomaintoolsDomainReputation
from domaintools.get_lookup_domain import DomaintoolsLookupDomain
from domaintools.get_pivot_action import DomaintoolsPivotAction
from domaintools.get_reverse_domain import DomaintoolsReverseDomain
from domaintools.get_reverse_email import DomaintoolsReverseEmail
from domaintools.get_reverse_ip import DomaintoolsReverseIP

if __name__ == "__main__":
    module = Module()

    module.register(DomaintoolsDomainReputation, "get_domain_reputation")
    module.register(DomaintoolsLookupDomain, "get_lookup_domain")
    module.register(DomaintoolsPivotAction, "get_pivot_action")
    module.register(DomaintoolsReverseDomain, "get_reverse_domain")
    module.register(DomaintoolsReverseEmail, "get_reverse_email")
    module.register(DomaintoolsReverseIP, "get_reverse_ip")

    module.run()
