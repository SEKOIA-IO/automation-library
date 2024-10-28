from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.alert_actions import CrowdstrikeActionCommentAlert, CrowdstrikeActionUpdateAlertStatus
from crowdstrike_falcon.custom_iocs import (
    CrowdstrikeActionBlockIOC,
    CrowdstrikeActionMonitorIOC,
    CrowdstrikeActionPushIOCsBlock,
    CrowdstrikeActionPushIOCsDetect,
)
from crowdstrike_falcon.event_stream_trigger import EventStreamTrigger
from crowdstrike_falcon.host_actions import CrowdstrikeActionDeIsolateHosts, CrowdstrikeActionIsolateHosts

if __name__ == "__main__":
    module = CrowdStrikeFalconModule()
    module.register(EventStreamTrigger, "event_stream_trigger")
    module.register(CrowdstrikeActionPushIOCsBlock, "push_iocs_block")
    module.register(CrowdstrikeActionPushIOCsDetect, "push_iocs_detect")
    module.register(CrowdstrikeActionBlockIOC, "block_ioc")
    module.register(CrowdstrikeActionMonitorIOC, "monitor_ioc")
    module.register(CrowdstrikeActionIsolateHosts, "isolate_hosts")
    module.register(CrowdstrikeActionDeIsolateHosts, "deisolate_hosts")

    module.register(CrowdstrikeActionUpdateAlertStatus, "alert_update_status")
    module.register(CrowdstrikeActionCommentAlert, "alert_add_comment")

    module.run()
