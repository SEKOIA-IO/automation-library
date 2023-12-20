from withsecure import WithSecureModule
from withsecure.isolate_device_from_network_action import IsolateDeviceFromNetworkAction
from withsecure.list_devices_action import ListDevicesAction
from withsecure.release_device_from_network_isolation_action import ReleaseDeviceFromNetworkIsolationAction
from withsecure.scan_device_for_malware import ScanDeviceForMalware
from withsecure.security_events_connector import SecurityEventsConnector
from withsecure.assign_device_profile_action import AssignDeviceProfileAction

if __name__ == "__main__":
    module = WithSecureModule()
    module.register(SecurityEventsConnector, "security_events_connector")
    module.register(IsolateDeviceFromNetworkAction, "isolate_device_from_network")
    module.register(ReleaseDeviceFromNetworkIsolationAction, "release_device_from_network_isolation")
    module.register(ScanDeviceForMalware, "scan_device_for_malware")
    module.register(AssignDeviceProfileAction, "assign_device_profile")
    module.register(ListDevicesAction, "list_devices")
    module.run()
