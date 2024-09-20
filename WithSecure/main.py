from withsecure import WithSecureModule
from withsecure.comment_incident import CommentIncident
from withsecure.enumerate_processes import EnumerateProcesses
from withsecure.isolate_device_from_network_action import IsolateDeviceFromNetworkAction
from withsecure.kill_process import KillProcess
from withsecure.kill_thread import KillThread
from withsecure.list_detections_for_incident import ListDetectionForIncident
from withsecure.list_devices_action import ListDevicesAction
from withsecure.release_device_from_network_isolation_action import ReleaseDeviceFromNetworkIsolationAction
from withsecure.scan_device_for_malware import ScanDeviceForMalware
from withsecure.security_events_connector import SecurityEventsConnector
from withsecure.update_incident_status import UpdateStatusIncident

if __name__ == "__main__":
    module = WithSecureModule()
    module.register(SecurityEventsConnector, "security_events_connector")
    module.register(IsolateDeviceFromNetworkAction, "isolate_device_from_network")
    module.register(ReleaseDeviceFromNetworkIsolationAction, "release_device_from_network_isolation")
    module.register(ScanDeviceForMalware, "scan_device_for_malware")
    module.register(ListDevicesAction, "list_devices")
    module.register(CommentIncident, "comment_incident")
    module.register(ListDetectionForIncident, "list_detections_for_incident")
    module.register(UpdateStatusIncident, "update_incident_status")
    module.register(EnumerateProcesses, "enumerate_processes")
    module.register(KillThread, "kill_thread")
    module.register(KillProcess, "kill_process")

    module.run()
