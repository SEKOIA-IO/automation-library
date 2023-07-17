from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_edr_events import SophosEDREventsTrigger
from sophos_module.trigger_sophos_xdr_query import SophosXDRIOCQuery

if __name__ == "__main__":
    module = SophosModule()
    module.register(SophosEDREventsTrigger, "sophos_events_trigger")
    module.register(SophosXDRIOCQuery, "sophos_query_ioc_trigger")
    module.run()
