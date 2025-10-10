from sekoia_automation.module import Module

from domaintools.get_domain_reputation import DomaintoolsDomainReputation
from domaintools.get_lookup_domain import DomaintoolsLookupDomain
from domaintools.get_pivot_action import DomaintoolsPivotAction
from domaintools.get_reverse_domain import DomaintoolsReverseDomain
from domaintools.get_reverse_email import DomaintoolsReverseEmail
from domaintools.get_reverse_ip import DomaintoolsReverseIP

if __name__ == "__main__":
    module = Module()

    module.register(DomaintoolsDomainReputation, "domaintools_get_domain_reputation")
    module.register(DomaintoolsLookupDomain, "domaintools_get_lookup_domain")
    module.register(DomaintoolsPivotAction, "domaintools_get_pivot_action")
    module.register(DomaintoolsReverseDomain, "domaintools_get_reverse_domain")
    module.register(DomaintoolsReverseEmail, "domaintools_get_reverse_email")
    module.register(DomaintoolsReverseIP, "domaintools_get_reverse_ip")

    module.run()
