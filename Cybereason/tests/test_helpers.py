from unittest.mock import MagicMock

from cybereason_modules.helpers import extract_models_from_malop, merge_suspicions, validate_response_not_login_failure
from tests.data import APP_HTML, EPP_MALOP_DETAIL, LOGIN_HTML


def test_extract_users_from_malop():
    assert list(extract_models_from_malop(EPP_MALOP_DETAIL, EPP_MALOP_DETAIL["users"], ".UserDetailsModel")) == [
        {
            "metadata": {"malopGuid": EPP_MALOP_DETAIL["guid"], "timestamp": EPP_MALOP_DETAIL["lastUpdateTime"]},
            "@class": ".UserDetailsModel",
            "guid": "AAAAGCaB05cjndzp",
            "displayName": "desktop-aaaaa\\system",
            "admin": False,
            "localSystem": False,
            "domainUser": False,
        }
    ]


def test_extract_machines_from_malop():
    assert list(extract_models_from_malop(EPP_MALOP_DETAIL, EPP_MALOP_DETAIL["machines"], ".MachineDetailsModel")) == [
        {
            "metadata": {"malopGuid": EPP_MALOP_DETAIL["guid"], "timestamp": EPP_MALOP_DETAIL["lastUpdateTime"]},
            "@class": ".MachineDetailsModel",
            "guid": "-1021733308.1198775089551518743",
            "displayName": "desktop-aaaaaa",
            "osType": "WINDOWS",
            "connected": False,
            "isolated": False,
            "lastConnected": 1668439428578,
            "adOU": None,
            "adOrganization": None,
            "adDisplayName": "DESKTOP-AAAAAA",
            "adDNSHostName": "desktop-aaaaaa.example.org",
            "adDepartment": None,
            "adCompany": None,
            "adLocation": None,
            "adMachineRole": None,
            "pylumId": "PYLUMCLIENT_INTEGRATION_DESKTOP-AAAAAA_005056B4A724",
            "empty": True,
        }
    ]


def test_merge_suspicions():
    suspicion1 = {
        "firstTimestamp": 1447276254985,
        "potentialEvidence": [
            "manyUnresolvedRecordNotExistsEvidence",
            "detectedInjectedEvidence",
            "highUnresolvedToResolvedRateEvidence",
        ],
        "totalSuspicions": 1,
    }
    suspicion2 = {
        "firstTimestamp": 1447276254000,
        "potentialEvidence": [
            "detectedInjectedEvidence",
            "hostingInjectedThreadEvidence",
            "highUnresolvedToResolvedRateEvidence",
        ],
        "totalSuspicions": 1,
    }

    assert merge_suspicions(suspicion1, None) == suspicion1
    assert merge_suspicions(None, suspicion2) == suspicion2
    suspicion = merge_suspicions(suspicion1, suspicion2)
    assert suspicion["firstTimestamp"] == 1447276254000
    assert sorted(suspicion["evidences"]) == [
        "detectedInjectedEvidence",
        "highUnresolvedToResolvedRateEvidence",
        "hostingInjectedThreadEvidence",
        "manyUnresolvedRecordNotExistsEvidence",
    ]


def test_validate_response_not_login_failure_on_json_content():
    response = MagicMock()
    response.content = b'{"key": "value"}'

    assert validate_response_not_login_failure(response) is True


def test_validate_response_not_login_failure_on_app_page():
    response = MagicMock()
    response.content = APP_HTML

    assert validate_response_not_login_failure(response) is True


def test_validate_response_not_login_failure_on_login_page():
    response = MagicMock()
    response.content = LOGIN_HTML

    assert validate_response_not_login_failure(response) is False
