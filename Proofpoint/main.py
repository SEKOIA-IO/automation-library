from sekoia_automation.module import Module

from proofpoint_modules.trigger_pod_events import PoDEventsTrigger
from proofpoint_modules.trigger_tap_events import TAPEventsTrigger

if __name__ == "__main__":
    module = Module()
    module.register(TAPEventsTrigger, "tap_events_trigger")
    module.register(PoDEventsTrigger, "pod_events_trigger")
    module.run()
