from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_edr_events import SophosEDREventsTrigger

if __name__ == "__main__":
    module = SophosModule()
    module.register(SophosEDREventsTrigger, "sophos_events_trigger")
    module.run()
