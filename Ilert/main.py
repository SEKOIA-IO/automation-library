# third parties
# internals
from sekoia_automation.module import Module

from ilert.action_ilert_trigger_alert import IlertTriggerAlertAction

if __name__ == "__main__":
    module = Module()
    module.register(IlertTriggerAlertAction, "ilert_trigger_alert")
    module.run()
