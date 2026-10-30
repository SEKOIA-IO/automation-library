from sekoia_automation.module import Module

from nextron_valhalla_sigma_rules_modules.models import (
    NextronValhallaSigmaRulesModuleConfiguration,
)
from nextron_valhalla_sigma_rules_modules.triggers.sync_sigma_rules_catalog import (
    SyncSigmaRulesCatalog,
)


class NextronValhallaSigmaRulesModule(Module):
    configuration: NextronValhallaSigmaRulesModuleConfiguration  # type: ignore[override]


__all__ = [
    "NextronValhallaSigmaRulesModule",
    "SyncSigmaRulesCatalog",
]
