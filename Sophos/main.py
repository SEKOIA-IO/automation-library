from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_edr_events import SophosEDREventsTrigger
from sophos_module.trigger_sophos_edr_events import SophosXDRQueryTrigger

if __name__ == "__main__":
    module = SophosModule()
    module.register(SophosEDREventsTrigger, "sophos_events_trigger")
    module.register(SophosXDRQueryTrigger, "sophos_query_events_trigger")
    module.run()
