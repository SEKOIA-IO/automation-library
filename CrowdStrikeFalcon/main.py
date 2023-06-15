from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.event_stream_trigger import EventStreamTrigger
from crowdstrike_falcon.custom_iocs import (
    CrowdstrikeActionPushIOCsBlock,
    CrowdstrikeActionPushIOCsDetect,
    CrowdstrikeActionBlockIOC,
    CrowdstrikeActionMonitorIOC,
)

if __name__ == "__main__":
    module = CrowdStrikeFalconModule()
    module.register(EventStreamTrigger, "event_stream_trigger")
    module.register(CrowdstrikeActionPushIOCsBlock, "push_iocs_block")
    module.register(CrowdstrikeActionPushIOCsDetect, "push_iocs_detect")
    module.register(CrowdstrikeActionBlockIOC, "block_ioc")
    module.register(CrowdstrikeActionMonitorIOC, "monitor_ioc")

    module.run()
