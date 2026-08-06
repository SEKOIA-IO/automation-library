from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests_mock
from sekoia_automation.storage import PersistentJSON

from zimperium_modules import ZimperiumModule
from zimperium_modules.connector_threats import MobileThreatDefenceConnector


@pytest.fixture
def trigger(data_storage):
    module = ZimperiumModule()
    module.configuration = {
        "client_id": "CLIENT_ID",
        "client_secret": "CLIENT_SECRET",
        "base_url": "https://example.com",
    }

    trigger = MobileThreatDefenceConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "intake_key": "intake_key",
        "frequency": 60,
        "start_time": 0,
        "timedelta": 0,
    }

    yield trigger


@pytest.fixture
def response_1():
    return {
        "content": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "accountId": "22222222-2222-2222-2222-222222222222",
                "teamId": "33333333-3333-3333-3333-333333333333",
                "teamName": "Default",
                "zappInstanceId": "44444444-4444-4444-4444-444444444444",
                "deviceId": "55555555-5555-5555-5555-555555555555",
                "device": {
                    "id": "55555555-5555-5555-5555-555555555555",
                    "mdmDeviceId": "",
                    "mamDeviceId": "",
                    "model": "Redacted",
                    "os": {"id": 1, "name": "ANDROID", "version": "16"},
                    "zdeviceId": "66666666-6666-6666-6666-666666666666",
                },
                "os": "android",
                "zappId": "77777777-7777-7777-7777-777777777777",
                "groupId": "88888888-8888-8888-8888-888888888888",
                "timestamp": 1773830431000,
                "timestampInfo": {
                    "timestamp": 1773830431000,
                    "toTheSecond": 1773830431000,
                    "toTheMinute": 1773830400000,
                    "toTheHour": 1773828000000,
                    "toTheDay": 1773792000000,
                },
                "eventReceivedTimestamp": 1773830433130,
                "eventProcessedTimestamp": 1773830433143,
                "timeTravel": "NONE",
                "threatTypeId": 172,
                "threatTypeName": "ACTIVE EXPLOIT OS ANDROID",
                "severity": 2,
                "severityName": "ELEVATED",
                "vector": 2,
                "vectorName": "Device",
                "categoryId": 64,
                "classification": 2,
                "classificationName": "RISKY",
                "state": 1,
                "responses": [
                    {
                        "responseId": 0,
                        "eventId": "99999999-9999-9999-9999-999999999999",
                        "timestamp": 1773830431000,
                    }
                ],
                "mitigationEvents": [],
                "generalInfo": {
                    "timeInterval": 2,
                    "deviceIp": "1.2.3.4",
                    "externalIp": "10.20.30.40",
                    "ssid": "",
                    "bssid": "02:00:00:00:00:00",
                    "actionTriggered": "Alert User",
                    "deviceTimestamp": 1773830431000,
                    "androidEnterpriseManagementState": {
                        "ownership": "PERSONALLY_OWNED",
                        "managementMode": "UNMANAGED",
                        "managementAppPackageName": "",
                        "workProfileState": "WORK_PROFILE_NOT_PRESENT",
                    },
                    "androidEnterpriseAccessNetworkState": [
                        {
                            "networkTransport": '["WIFI"]',
                            "wifiSecurityLevel": "PERSONAL",
                            "privateDnsState": "ACTIVE",
                        }
                    ],
                },
                "locationInfo": {
                    "geoPoint": {"lat": 20.0000, "lon": 20.0000},
                    "source": "GEOIP",
                    "city": "Redacted",
                    "country": "France",
                },
                "suspiciousUrlInfo": {},
                "arpTablesInfo": {"before": []},
                "runningServices": [],
                "networkStatistics": [],
                "nearByNetworks": [],
                "processList": [
                    {
                        "service": "n/a",
                        "user": "10286",
                        "processId": "9938",
                        "parentProcessId": "1474",
                        "processName": ".zimperium.zips",
                    }
                ],
                "simulated": False,
                "lastModified": 1773830431000,
                "detectionFiles": [],
                "activationName": "john.doe@company.com",
                "agentType": 2,
                "deviceOwner": "john.doe@company.com",
                "policiesInfo": [
                    {
                        "type": "App Policy Android v2",
                        "hash": "64351b6847c6925629977111ffad0afd",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "App Settings",
                        "hash": "6f09229e2298bbb9aea532783e5fb292",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Network Policy",
                        "hash": "ddd40425296c539823863221adda7c4a",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "OS Risk",
                        "hash": "331f6baad5f6a48a0038800da9480592",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Phishing",
                        "hash": "9ef362e0c1be90c4067928c8ca3148f4",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Privacy",
                        "hash": "55386c63025ffe18b01edac0cf95d116",
                        "deployedAt": 1773781889000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Threat Android",
                        "hash": "26e9ec7025d157aa74ed714c9a285309",
                        "deployedAt": 1773781843000,
                        "downloadedAt": 1773830428000,
                    },
                ],
                "triggeredActions": [
                    {
                        "actionType": 0,
                        "actionTypeName": "ALERT_USER",
                        "actionMetadata": None,
                    }
                ],
                "zeventId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "zappInstance": {
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "MTD",
                    "bundleId": "com.zimperium.zips",
                    "version": "5.9.22",
                    "buildNumber": "0.260116182",
                    "zversion": "5.9.22",
                    "zbuildNumber": "26011618",
                },
            },
            {
                "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "accountId": "22222222-2222-2222-2222-222222222222",
                "teamId": "33333333-3333-3333-3333-333333333333",
                "teamName": "Default",
                "zappInstanceId": "44444444-4444-4444-4444-444444444444",
                "deviceId": "55555555-5555-5555-5555-555555555555",
                "device": {
                    "id": "55555555-5555-5555-5555-555555555555",
                    "mdmDeviceId": "",
                    "mamDeviceId": "",
                    "model": "Redacted",
                    "os": {"id": 1, "name": "ANDROID", "version": "16"},
                    "zdeviceId": "66666666-6666-6666-6666-666666666666",
                },
                "os": "android",
                "zappId": "77777777-7777-7777-7777-777777777777",
                "groupId": "88888888-8888-8888-8888-888888888888",
                "timestamp": 1773830432000,
                "timestampInfo": {
                    "timestamp": 1773830432000,
                    "toTheSecond": 1773830432000,
                    "toTheMinute": 1773830400000,
                    "toTheHour": 1773828000000,
                    "toTheDay": 1773792000000,
                },
                "eventReceivedTimestamp": 1773830433252,
                "eventProcessedTimestamp": 1773830433265,
                "timeTravel": "NONE",
                "threatTypeId": 50,
                "threatTypeName": "PASSCODE NOT ENABLED",
                "severity": 2,
                "severityName": "ELEVATED",
                "vector": 2,
                "vectorName": "Device",
                "categoryId": 32,
                "classification": 2,
                "classificationName": "RISKY",
                "state": 1,
                "responses": [
                    {
                        "responseId": 0,
                        "eventId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "timestamp": 1773830432000,
                    }
                ],
                "mitigationEvents": [],
                "generalInfo": {
                    "timeInterval": 3,
                    "deviceIp": "1.2.3.4",
                    "externalIp": "10.20.30.40",
                    "ssid": "",
                    "bssid": "02:00:00:00:00:00",
                    "actionTriggered": "Alert User",
                    "deviceTimestamp": 1773830432000,
                    "androidEnterpriseManagementState": {
                        "ownership": "PERSONALLY_OWNED",
                        "managementMode": "UNMANAGED",
                        "managementAppPackageName": "",
                        "workProfileState": "WORK_PROFILE_NOT_PRESENT",
                    },
                    "androidEnterpriseAccessNetworkState": [
                        {
                            "networkTransport": '["WIFI"]',
                            "wifiSecurityLevel": "PERSONAL",
                            "privateDnsState": "ACTIVE",
                        }
                    ],
                },
                "locationInfo": {
                    "geoPoint": {"lat": 20.0000, "lon": 20.0000},
                    "source": "GEOIP",
                    "city": "Redacted",
                    "country": "France",
                },
                "suspiciousUrlInfo": {},
                "arpTablesInfo": {"before": []},
                "runningServices": [],
                "networkStatistics": [],
                "nearByNetworks": [],
                "processList": [
                    {
                        "service": "n/a",
                        "user": "10286",
                        "processId": "9938",
                        "parentProcessId": "1474",
                        "processName": ".zimperium.zips",
                    }
                ],
                "simulated": False,
                "lastModified": 1773830432000,
                "detectionFiles": [],
                "activationName": "john.doe@company.com",
                "agentType": 2,
                "deviceOwner": "john.doe@company.com",
                "policiesInfo": [
                    {
                        "type": "App Policy Android v2",
                        "hash": "64351b6847c6925629977111ffad0afd",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "App Settings",
                        "hash": "6f09229e2298bbb9aea532783e5fb292",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Network Policy",
                        "hash": "ddd40425296c539823863221adda7c4a",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "OS Risk",
                        "hash": "331f6baad5f6a48a0038800da9480592",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Phishing",
                        "hash": "9ef362e0c1be90c4067928c8ca3148f4",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Privacy",
                        "hash": "55386c63025ffe18b01edac0cf95d116",
                        "deployedAt": 1773781889000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Threat Android",
                        "hash": "26e9ec7025d157aa74ed714c9a285309",
                        "deployedAt": 1773781843000,
                        "downloadedAt": 1773830428000,
                    },
                ],
                "triggeredActions": [
                    {
                        "actionType": 0,
                        "actionTypeName": "ALERT_USER",
                        "actionMetadata": None,
                    }
                ],
                "zeventId": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                "zappInstance": {
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "MTD",
                    "bundleId": "com.zimperium.zips",
                    "version": "5.9.22",
                    "buildNumber": "0.260116182",
                    "zversion": "5.9.22",
                    "zbuildNumber": "26011618",
                },
            },
            {
                "id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                "accountId": "22222222-2222-2222-2222-222222222222",
                "teamId": "33333333-3333-3333-3333-333333333333",
                "teamName": "Default",
                "zappInstanceId": "44444444-4444-4444-4444-444444444444",
                "deviceId": "55555555-5555-5555-5555-555555555555",
                "device": {
                    "id": "55555555-5555-5555-5555-555555555555",
                    "mdmDeviceId": "",
                    "mamDeviceId": "",
                    "model": "Redacted",
                    "os": {"id": 1, "name": "ANDROID", "version": "16"},
                    "zdeviceId": "66666666-6666-6666-6666-666666666666",
                },
                "os": "android",
                "zappId": "77777777-7777-7777-7777-777777777777",
                "groupId": "88888888-8888-8888-8888-888888888888",
                "timestamp": 1773830430000,
                "timestampInfo": {
                    "timestamp": 1773830430000,
                    "toTheSecond": 1773830430000,
                    "toTheMinute": 1773830400000,
                    "toTheHour": 1773828000000,
                    "toTheDay": 1773792000000,
                },
                "eventReceivedTimestamp": 1773830431818,
                "eventProcessedTimestamp": 1773830431831,
                "timeTravel": "NONE",
                "threatTypeId": 223,
                "threatTypeName": "BIOMETRIC AUTH DISABLED",
                "severity": 2,
                "severityName": "ELEVATED",
                "vector": 2,
                "vectorName": "Device",
                "categoryId": 131,
                "classification": 2,
                "classificationName": "RISKY",
                "state": 1,
                "responses": [
                    {
                        "responseId": 0,
                        "eventId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                        "timestamp": 1773830430000,
                    }
                ],
                "mitigationEvents": [],
                "generalInfo": {
                    "timeInterval": 1,
                    "deviceIp": "1.2.3.4",
                    "externalIp": "10.20.30.40",
                    "ssid": "",
                    "bssid": "02:00:00:00:00:00",
                    "actionTriggered": "Alert User",
                    "deviceTimestamp": 1773830430000,
                    "androidEnterpriseManagementState": {
                        "ownership": "PERSONALLY_OWNED",
                        "managementMode": "UNMANAGED",
                        "managementAppPackageName": "",
                        "workProfileState": "WORK_PROFILE_NOT_PRESENT",
                    },
                    "androidEnterpriseAccessNetworkState": [
                        {
                            "networkTransport": '["WIFI"]',
                            "wifiSecurityLevel": "PERSONAL",
                            "privateDnsState": "ACTIVE",
                        }
                    ],
                },
                "locationInfo": {
                    "geoPoint": {"lat": 20.0000, "lon": 20.0000},
                    "source": "GEOIP",
                    "city": "Redacted",
                    "country": "France",
                },
                "suspiciousUrlInfo": {},
                "arpTablesInfo": {"before": []},
                "runningServices": [],
                "networkStatistics": [],
                "nearByNetworks": [],
                "processList": [
                    {
                        "service": "n/a",
                        "user": "10286",
                        "processId": "9938",
                        "parentProcessId": "1474",
                        "processName": ".zimperium.zips",
                    }
                ],
                "additionalPublicForensics": [
                    {
                        "key": "Reason",
                        "value": "Strong biometric authentication not configured",
                    }
                ],
                "simulated": False,
                "lastModified": 1773830430000,
                "detectionFiles": [],
                "activationName": "john.doe@company.com",
                "agentType": 2,
                "deviceOwner": "john.doe@company.com",
                "policiesInfo": [
                    {
                        "type": "App Policy Android v2",
                        "hash": "64351b6847c6925629977111ffad0afd",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "App Settings",
                        "hash": "6f09229e2298bbb9aea532783e5fb292",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Network Policy",
                        "hash": "ddd40425296c539823863221adda7c4a",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "OS Risk",
                        "hash": "331f6baad5f6a48a0038800da9480592",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Phishing",
                        "hash": "9ef362e0c1be90c4067928c8ca3148f4",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Privacy",
                        "hash": "55386c63025ffe18b01edac0cf95d116",
                        "deployedAt": 1773781889000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Threat Android",
                        "hash": "26e9ec7025d157aa74ed714c9a285309",
                        "deployedAt": 1773781843000,
                        "downloadedAt": 1773830428000,
                    },
                ],
                "triggeredActions": [
                    {
                        "actionType": 0,
                        "actionTypeName": "ALERT_USER",
                        "actionMetadata": None,
                    }
                ],
                "zeventId": "11111111-2222-3333-4444-555555555555",
                "zappInstance": {
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "MTD",
                    "bundleId": "com.zimperium.zips",
                    "version": "5.9.22",
                    "buildNumber": "0.260116182",
                    "zversion": "5.9.22",
                    "zbuildNumber": "26011618",
                },
            },
            {
                "id": "66666666-7777-8888-9999-000000000000",
                "accountId": "22222222-2222-2222-2222-222222222222",
                "teamId": "33333333-3333-3333-3333-333333333333",
                "teamName": "Default",
                "zappInstanceId": "44444444-4444-4444-4444-444444444444",
                "deviceId": "55555555-5555-5555-5555-555555555555",
                "device": {
                    "id": "55555555-5555-5555-5555-555555555555",
                    "mdmDeviceId": "",
                    "mamDeviceId": "",
                    "model": "Redacted",
                    "os": {"id": 1, "name": "ANDROID", "version": "16"},
                    "zdeviceId": "66666666-6666-6666-6666-666666666666",
                },
                "os": "android",
                "zappId": "77777777-7777-7777-7777-777777777777",
                "groupId": "88888888-8888-8888-8888-888888888888",
                "timestamp": 1773830453000,
                "timestampInfo": {
                    "timestamp": 1773830453000,
                    "toTheSecond": 1773830453000,
                    "toTheMinute": 1773830400000,
                    "toTheHour": 1773828000000,
                    "toTheDay": 1773792000000,
                },
                "eventReceivedTimestamp": 1773830455006,
                "eventProcessedTimestamp": 1773830455019,
                "timeTravel": "NONE",
                "threatTypeId": 142,
                "threatTypeName": "STORAGE PERMISSION REQUIRED",
                "severity": 2,
                "severityName": "ELEVATED",
                "vector": 2,
                "vectorName": "Device",
                "categoryId": 131,
                "classification": 2,
                "classificationName": "RISKY",
                "state": 4,
                "responses": [
                    {
                        "responseId": 0,
                        "eventId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "timestamp": 1773830453000,
                    }
                ],
                "mitigationEvents": [],
                "generalInfo": {
                    "timeInterval": 24,
                    "deviceIp": "1.2.3.4",
                    "externalIp": "10.20.30.40",
                    "ssid": "SCorp",
                    "bssid": "11:22:33:44:55:66",
                    "actionTriggered": "Alert User",
                    "deviceTimestamp": 1773830453000,
                    "androidEnterpriseManagementState": {
                        "ownership": "PERSONALLY_OWNED",
                        "managementMode": "UNMANAGED",
                        "managementAppPackageName": "",
                        "workProfileState": "WORK_PROFILE_NOT_PRESENT",
                    },
                    "androidEnterpriseAccessNetworkState": [
                        {
                            "networkTransport": '["WIFI"]',
                            "wifiSecurityLevel": "PERSONAL",
                            "privateDnsState": "ACTIVE",
                        }
                    ],
                },
                "locationInfo": {
                    "geoPoint": {"lat": 20.0000, "lon": 20.0000},
                    "source": "GEOIP",
                    "city": "Redacted",
                    "country": "France",
                },
                "suspiciousUrlInfo": {},
                "arpTablesInfo": {"before": []},
                "runningServices": [],
                "networkStatistics": [],
                "nearByNetworks": [],
                "processList": [
                    {
                        "service": "n/a",
                        "user": "10286",
                        "processId": "9938",
                        "parentProcessId": "1474",
                        "processName": ".zimperium.zips",
                    }
                ],
                "simulated": False,
                "mitigatedAt": 1773830476518,
                "mitigatedReason": "",
                "lastModified": 1773830508709,
                "detectionFiles": [],
                "activationName": "john.doe@company.com",
                "agentType": 2,
                "deviceOwner": "john.doe@company.com",
                "policiesInfo": [
                    {
                        "type": "App Policy Android v2",
                        "hash": "64351b6847c6925629977111ffad0afd",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "App Settings",
                        "hash": "6f09229e2298bbb9aea532783e5fb292",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Network Policy",
                        "hash": "ddd40425296c539823863221adda7c4a",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "OS Risk",
                        "hash": "331f6baad5f6a48a0038800da9480592",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Phishing",
                        "hash": "9ef362e0c1be90c4067928c8ca3148f4",
                        "deployedAt": 1773767334000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Privacy",
                        "hash": "55386c63025ffe18b01edac0cf95d116",
                        "deployedAt": 1773781889000,
                        "downloadedAt": 1773830428000,
                    },
                    {
                        "type": "Threat Android",
                        "hash": "26e9ec7025d157aa74ed714c9a285309",
                        "deployedAt": 1773781843000,
                        "downloadedAt": 1773830428000,
                    },
                ],
                "triggeredActions": [
                    {
                        "actionType": 0,
                        "actionTypeName": "ALERT_USER",
                        "actionMetadata": None,
                    }
                ],
                "zeventId": "ffffffff-aaaa-bbbb-cccc-dddddddddddd",
                "zappInstance": {
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "MTD",
                    "bundleId": "com.zimperium.zips",
                    "version": "5.9.22",
                    "buildNumber": "0.260116182",
                    "zversion": "5.9.22",
                    "zbuildNumber": "26011618",
                },
            },
        ],
        "pageable": {
            "pageNumber": 0,
            "pageSize": 20,
            "sort": {"unsorted": True, "sorted": False, "empty": True},
            "offset": 0,
            "unpaged": False,
            "paged": True,
        },
        "totalPages": 1,
        "totalElements": 4,
        "last": True,
        "numberOfElements": 4,
        "first": True,
        "sort": {"unsorted": True, "sorted": False, "empty": True},
        "number": 0,
        "size": 20,
        "empty": False,
    }


@pytest.fixture
def trigger_activation() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def end_time(trigger_activation: datetime) -> datetime:
    return trigger_activation


@pytest.fixture
def start_time(trigger_activation: datetime) -> datetime:
    return trigger_activation - timedelta(minutes=1)


def test_fetch_events(
    trigger,
    response_1: dict,
    start_time: datetime,
    end_time: datetime,
) -> None:
    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://example.com/api/auth/v1/api_keys/login",
            status_code=200,
            json={"accessToken": "TOKEN1", "refreshToken": "TOKEN2"},
        )

        mock_requests.get(
            "https://example.com/api/threats/public/v1/threats",
            status_code=200,
            json=response_1,
        )

        batches = list(trigger.fetch_events(from_date=start_time, to_date=end_time))
        assert len(batches) == 1

        events = batches[0]
        assert len(events) == 4


def test_stepper_with_cursor(trigger, data_storage):
    date = datetime.now(UTC)
    most_recent_date_requested = date - timedelta(days=6)
    context = PersistentJSON("context.json", data_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("zimperium_modules.connector_threats.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now(UTC)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == most_recent_date_requested


def test_stepper_with_cursor_older_than_week(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    fixed_now = datetime(2026, 3, 16, 1, 12, 0, tzinfo=UTC)
    most_recent_date_requested = fixed_now - timedelta(days=40)
    expected_date = fixed_now - timedelta(days=7)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("zimperium_modules.connector_threats.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start.replace(microsecond=0) == expected_date.replace(microsecond=0)


def test_stepper_without_cursor(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_requested"] = None

    with patch("sekoia_automation.helpers.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=UTC)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == datetime(2023, 3, 22, 11, 55, 28, tzinfo=UTC)
