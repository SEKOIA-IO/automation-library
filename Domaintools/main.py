from sekoia_automation.module import Module

from domaintools_modules.get_domain_reputation import DomaintoolsDomainReputation
from domaintools_modules.get_lookup_domain import DomaintoolsLookupDomain
from domaintools_modules.get_pivot_action import DomaintoolsPivotAction
from domaintools_modules.get_reverse_domain import DomaintoolsReverseDomain
from domaintools_modules.get_reverse_email import DomaintoolsReverseEmail
from domaintools_modules.get_reverse_ip import DomaintoolsReverseIP

if __name__ == "__main__":
    module = Module()

    module.register(DomaintoolsDomainReputation, "domaintools_get_domain_reputation")
    module.register(DomaintoolsLookupDomain, "domaintools_get_lookup_domain")
    module.register(DomaintoolsPivotAction, "domaintools_get_pivot_action")
    module.register(DomaintoolsReverseDomain, "domaintools_get_reverse_domain")
    module.register(DomaintoolsReverseEmail, "thehive_create_alert")
    module.register(DomaintoolsReverseIP, "domaintools_get_reverse_email")

    module.run()
