import requests
from sekoia_automation.action import GenericAPIAction

from aether_endpoint_security_api.base import AuthorizationMixin


class AetherAction(GenericAPIAction, AuthorizationMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_credentials: dict | None = None
        self.http_session: requests.Session = requests.Session()

    def get_headers(self):
        return {
            "Accept": "application/json",
            "Authorization": self._get_authorization(),
            "WatchGuard-API-Key": self.module.configuration["api_key"],
            "Content-Type": "application/json",
        }

    def get_body(self, arguments: dict):
        return None

    def run(self, arguments: dict) -> dict | None:
        # copy account_id argument (set in the module configuration like the API key) in the list of arguments
        new_arguments = {
            "account_id": self.module.configuration["account_id"],
            **arguments,
        }
        return super().run(new_arguments)


base_url = "rest/aether-endpoint-security/aether-mgmt/"


class RetrievesListOfDevices(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/devices"
    query_parameters: list[str] = []
    timeout: int = 120


class SendsActionToDevices(AetherAction):
    verb = "post"
    endpoint = base_url + "api/v1/accounts/{account_id}/devices/action"
    query_parameters: list[str] = []
    timeout: int = 120


class IsolatesDevices(AetherAction):
    verb = "post"
    endpoint = base_url + "api/v1/accounts/{account_id}/devices/isolation"
    query_parameters: list[str] = []
    timeout: int = 120


class StopsDeviceIsolation(AetherAction):
    verb = "post"
    endpoint = base_url + "api/v1/accounts/{account_id}/devices/noisolation"
    query_parameters: list[str] = []
    timeout: int = 120


class UninstallsProtectionFromDevices(AetherAction):
    verb = "post"
    endpoint = base_url + "api/v1/accounts/{account_id}/devices/uninstall"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesDeviceProtectionStatus(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/devicesprotectionstatus"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesFullEncryptionModuleStatus(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/encryptionstatistics"
    query_parameters: list[str] = []
    timeout: int = 60


class ScansDevicesImmediately(AetherAction):
    verb = "post"
    endpoint = base_url + "api/v1/accounts/{account_id}/immediatescan"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesListOfManagedConfigurations(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/managedconfigurations/{type}"
    query_parameters: list[str] = []
    timeout: int = 120


class LinksDevicesToManagedConfiguration(AetherAction):
    verb = "patch"
    endpoint = base_url + "api/v1/accounts/{account_id}/managedconfigurations/{type}/{config_id}"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesPatchManagementModuleStatus(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/patchmanagementstatistics"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesCountsOfSecurityEvents(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/securityeventcounters/{type}"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesListOfSecurityEventsForSpecificDevices(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/securityevents/{type}/export/{period}"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesSecurityOverviewInformation(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/securityoverview/{period}"
    query_parameters: list[str] = []
    timeout: int = 120


class RetrievesListOfUnmanagedDevices(AetherAction):
    verb = "get"
    endpoint = base_url + "api/v1/accounts/{account_id}/unmanageddevices"
    query_parameters: list[str] = []
    timeout: int = 120
