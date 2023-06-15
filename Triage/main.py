from sekoia_automation.module import Module

from triage_modules.action_triage_to_observables import TriageToObservablesAction
from triage_modules.trigger_triage import TriageConfigsTrigger

if __name__ == "__main__":
    module = Module()
    module.register(TriageConfigsTrigger, "trigger_triage_configs")
    module.register(TriageToObservablesAction, "triage_to_observables")
    module.run()
