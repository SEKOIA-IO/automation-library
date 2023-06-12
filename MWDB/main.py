from sekoia_automation.module import Module

from mwdb_module.action_config_to_observables import ConfigToObservablesAction
from mwdb_module.triggers import MWDBConfigsTrigger

if __name__ == "__main__":
    module = Module()
    module.register(MWDBConfigsTrigger, "trigger_mwdb_configs")
    module.register(ConfigToObservablesAction, "config_to_observables")
    module.run()
