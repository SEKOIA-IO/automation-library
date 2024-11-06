from sophos_module.action_sophos_edr_deisolate import ActionSophosEDRDeIsolateEndpoint
from sophos_module.action_sophos_edr_isolate import ActionSophosEDRIsolateEndpoint
from sophos_module.action_sophos_edr_run_scan import ActionSophosEDRScan
from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_edr_events import SophosEDREventsTrigger
from sophos_module.trigger_sophos_xdr_query import SophosXDRIOCQuery

if __name__ == "__main__":
    module = SophosModule()
    module.register(SophosEDREventsTrigger, "sophos_events_trigger")
    module.register(SophosXDRIOCQuery, "sophos_query_ioc_trigger")
    module.register(ActionSophosEDRIsolateEndpoint, "sophos_edr_isolate_endpoint")
    module.register(ActionSophosEDRDeIsolateEndpoint, "sophos_edr_deisolate_endpoint")
    module.register(ActionSophosEDRScan, "sophos_edr_run_scan")

    module.run()
