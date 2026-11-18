from sekoia_automation.module import Module

from nextron_valhalla_modules.models import (
    NextronValhallaModuleConfiguration,
)
from nextron_valhalla_modules.triggers.sync_sigma_rules_catalog import (
    SyncSigmaRulesCatalog,
)


class NextronValhallaModule(Module):
    configuration: NextronValhallaModuleConfiguration  # type: ignore[override]


__all__ = [
    "NextronValhallaModule",
    "SyncSigmaRulesCatalog",
]
