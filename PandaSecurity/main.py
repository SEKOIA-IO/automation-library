from sekoia_automation.module import Module

from aether_endpoint_security_api import (
    IsolatesDevices,
    LinksDevicesToManagedConfiguration,
    RetrievesCountsOfSecurityEvents,
    RetrievesDeviceProtectionStatus,
    RetrievesFullEncryptionModuleStatus,
    RetrievesListOfDevices,
    RetrievesListOfManagedConfigurations,
    RetrievesListOfSecurityEventsForSpecificDevices,
    RetrievesListOfUnmanagedDevices,
    RetrievesPatchManagementModuleStatus,
    RetrievesSecurityOverviewInformation,
    ScansDevicesImmediately,
    SendsActionToDevices,
    StopsDeviceIsolation,
    UninstallsProtectionFromDevices,
)
from aether_endpoint_security_api.trigger_security_events import AetherSecurityEventsTrigger

if __name__ == "__main__":
    module = Module()
    module.register(RetrievesListOfDevices, "get-api/v1/accounts/{account_id}/devices")
    module.register(SendsActionToDevices, "post-api/v1/accounts/{account_id}/devices/action")
    module.register(IsolatesDevices, "post-api/v1/accounts/{account_id}/devices/isolation")
    module.register(StopsDeviceIsolation, "post-api/v1/accounts/{account_id}/devices/noisolation")
    module.register(
        UninstallsProtectionFromDevices,
        "post-api/v1/accounts/{account_id}/devices/uninstall",
    )
    module.register(
        RetrievesDeviceProtectionStatus,
        "get-api/v1/accounts/{account_id}/devicesprotectionstatus",
    )
    module.register(
        RetrievesFullEncryptionModuleStatus,
        "get-api/v1/accounts/{account_id}/encryptionstatistics",
    )
    module.register(ScansDevicesImmediately, "post-api/v1/accounts/{account_id}/immediatescan")
    module.register(
        RetrievesListOfManagedConfigurations,
        "get-api/v1/accounts/{account_id}/managedconfigurations/{type}",
    )
    module.register(
        LinksDevicesToManagedConfiguration,
        "patch-api/v1/accounts/{account_id}/managedconfigurations/{type}/{config_id}",
    )
    module.register(
        RetrievesPatchManagementModuleStatus,
        "get-api/v1/accounts/{account_id}/patchmanagementstatistics",
    )
    module.register(
        RetrievesCountsOfSecurityEvents,
        "get-api/v1/accounts/{account_id}/securityeventcounters/{type}",
    )
    module.register(
        RetrievesListOfSecurityEventsForSpecificDevices,
        "get-api/v1/accounts/{account_id}/securityevents/{type}/export/{period}",
    )
    module.register(
        RetrievesSecurityOverviewInformation,
        "get-api/v1/accounts/{account_id}/securityoverview/{period}",
    )
    module.register(
        RetrievesListOfUnmanagedDevices,
        "get-api/v1/accounts/{account_id}/unmanageddevices",
    )
    module.register(AetherSecurityEventsTrigger, "security_events_trigger")
    module.run()
