# third parties
# internals
from sekoia_automation.module import Module

from pagerduty.action_pagerduty_trigger_alert import PagerDutyTriggerAlertAction

if __name__ == "__main__":
    module = Module()
    module.register(PagerDutyTriggerAlertAction, "pagerduty_trigger_alert")
    module.run()
