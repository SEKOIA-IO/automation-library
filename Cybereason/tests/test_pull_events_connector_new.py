import copy
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from cybereason_modules import CybereasonModule
from cybereason_modules.connector_pull_events_new import CybereasonEventConnectorNew
from cybereason_modules.exceptions import InvalidResponse, LoginFailureError
from tests.data import EDR_MALOP, EDR_MALOP_SUSPICIONS_RESULTS, EPP_MALOP, EPP_MALOP_DETAIL, LOGIN_HTML


@pytest.fixture
def fake_time():
    yield 1666180800


@pytest.fixture
def patch_time(fake_time):
    with patch("cybereason_modules.connector_pull_events.time") as mock_time:
        mock_time.time.return_value = fake_time
        yield mock_time


@pytest.fixture
def mock_cybereason_api():
    with requests_mock.Mocker() as mock:
        jar = requests_mock.CookieJar()
        jar.set("JSESSIONID", "session_id", domain="fake.cybereason.net")
        mock.post(
            "https://fake.cybereason.net/login.html",
            status_code=200,
            cookies=jar,
        )
        yield mock


@pytest.fixture
def suspicions():
    return {
        (1495442710604, "shellOfNonShellRunnerSuspicion"): {
            "firstTimestamp": 1447276254985,
            "potentialEvidence": [
                "detectedInjectedEvidence",
                "highUnresolvedToResolvedRateEvidence",
                "hostingInjectedThreadEvidence",
                "manyUnresolvedRecordNotExistsEvidence",
            ],
            "totalSuspicions": 1,
        },
        (1495442710605, "mimikatzExecutionPSESuspicion"): {
            "firstTimestamp": 1629438188575,
            "potentialEvidence": ["mimikatzExecutionPSEEvidence"],
            "totalSuspicions": 1,
        },
    }


@pytest.fixture
def epp_machines():
    metadata = {"metadata": {"malopGuid": EPP_MALOP["guid"], "timestamp": EPP_MALOP["lastUpdateTime"]}}

    machines = []
    for machine in EPP_MALOP_DETAIL["machines"]:
        model = copy.deepcopy(machine)
        model["@class"] = ".MachineDetailsModel"
        model.update(metadata)
        machines.append(model)

    return machines


@pytest.fixture
def epp_users():
    metadata = {"metadata": {"malopGuid": EPP_MALOP["guid"], "timestamp": EPP_MALOP["lastUpdateTime"]}}

    users = []
    for user in EPP_MALOP_DETAIL["users"]:
        model = copy.deepcopy(user)
        model["@class"] = ".UserDetailsModel"
        model.update(metadata)
        users.append(model)

    return users


@pytest.fixture
def epp_file_suspects():
    metadata = {"metadata": {"malopGuid": EPP_MALOP["guid"], "timestamp": EPP_MALOP["lastUpdateTime"]}}

    files = []
    for file in EPP_MALOP_DETAIL["fileSuspects"]:
        model = copy.deepcopy(file)
        model["@class"] = ".FileSuspectDetailsModel"
        model.update(metadata)
        files.append(model)

    return files


@pytest.fixture
def epp_malop_detail():
    malop = copy.deepcopy(EPP_MALOP_DETAIL)
    malop.pop("users")
    malop.pop("machines")
    malop.pop("fileSuspects")
    return malop


@pytest.fixture
def edr_machines():
    metadata = {"metadata": {"malopGuid": EDR_MALOP["guid"], "timestamp": EDR_MALOP["lastUpdateTime"]}}

    machines = []
    for machine in EDR_MALOP["machines"]:
        model = copy.deepcopy(machine)
        model["@class"] = ".MachineInboxModel"
        model.update(metadata)
        machines.append(model)

    return machines


@pytest.fixture
def edr_users():
    metadata = {"metadata": {"malopGuid": EDR_MALOP["guid"], "timestamp": EDR_MALOP["lastUpdateTime"]}}

    users = []
    for user in EDR_MALOP["users"]:
        model = copy.deepcopy(user)
        model["@class"] = ".UserInboxModel"
        model.update(metadata)
        users.append(model)

    return users


@pytest.fixture
def edr_malop():
    malop = copy.deepcopy(EDR_MALOP)
    malop.pop("users")
    malop.pop("machines")
    return malop


@pytest.fixture
def edr_suspicions():
    return [
        {
            "metadata": {"malopGuid": EDR_MALOP["guid"], "timestamp": EDR_MALOP["lastUpdateTime"]},
            "@class": ".SuspicionModel",
            "guid": 1495442710604,
            "name": "shellOfNonShellRunnerSuspicion",
            "firstTimestamp": 1447276254985,
            "evidences": [
                "detectedInjectedEvidence",
                "highUnresolvedToResolvedRateEvidence",
                "hostingInjectedThreadEvidence",
                "manyUnresolvedRecordNotExistsEvidence",
            ],
        },
        {
            "metadata": {"malopGuid": EDR_MALOP["guid"], "timestamp": EDR_MALOP["lastUpdateTime"]},
            "@class": ".SuspicionModel",
            "guid": 1495442710605,
            "name": "mimikatzExecutionPSESuspicion",
            "firstTimestamp": 1629438188575,
            "evidences": ["mimikatzExecutionPSEEvidence"],
        },
    ]


@pytest.fixture
def trigger(symphony_storage, patch_time):
    module = CybereasonModule()
    trigger = CybereasonEventConnectorNew(module=module, data_path=symphony_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://fake.cybereason.net",
        "username": "username",
        "password": "password",
    }
    trigger.configuration = {"intake_key": "intake_key", "frequency": 60, "chunk_size": 20}
    return trigger


def test_fetch_malops(trigger, mock_cybereason_api):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/mmng/v2/malops",
        status_code=200,
        json={"data": {"data": [EPP_MALOP, EDR_MALOP]}},
    )

    assert trigger.fetch_malops(0, 9999999) == [EPP_MALOP, EDR_MALOP]


def test_fetch_malops_empty(trigger, mock_cybereason_api):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/mmng/v2/malops",
        status_code=404,
        content=None,
    )

    assert trigger.fetch_malops(0, 9999999) == []


def test_fetch_malops_failed(trigger, mock_cybereason_api):
    mock_cybereason_api.post("https://fake.cybereason.net/rest/mmng/v2/malops", status_code=204, json={})

    with pytest.raises(InvalidResponse):
        trigger.fetch_malops(0, 999999)


def consolidate_suspicions(suspicions: dict[tuple[str, str], dict[str, Any]]):
    normalized_suspicions = {}

    for suspicion_id in suspicions.keys():
        normalized_suspicions[suspicion_id] = suspicions[suspicion_id]
        normalized_suspicions[suspicion_id]["potentialEvidence"] = sorted(
            suspicions[suspicion_id]["potentialEvidence"]
        )

    return normalized_suspicions


def test_get_edr_malop_suspicions(trigger, mock_cybereason_api, suspicions):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/crimes/unified",
        status_code=200,
        json=EDR_MALOP_SUSPICIONS_RESULTS,
    )

    malop_suspicions = trigger.get_edr_malop_suspicions("11.1882697476172655933", "MalopProcess")

    assert malop_suspicions is not None
    assert suspicions == consolidate_suspicions(malop_suspicions)


def test_get_edr_malop_suspicions_with_no_result(trigger, mock_cybereason_api):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/crimes/unified",
        status_code=200,
        json={"data": {"resultIdToElementDataMap": {"00.00000000000000000000": {}}}},
    )

    assert trigger.get_edr_malop_suspicions("11.1882697476172655933", "MalopProcess") is None


def test_get_edr_malop_suspicions_with_no_suspicions(trigger, mock_cybereason_api):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/crimes/unified",
        status_code=200,
        json={"data": {"resultIdToElementDataMap": {"11.1882697476172655933": {"suspicions": None}}}},
    )

    assert trigger.get_edr_malop_suspicions("11.1882697476172655933", "MalopProcess") is None


def test_fetch_last_events(
    trigger,
    fake_time,
    mock_cybereason_api,
    epp_malop_detail,
    epp_machines,
    epp_users,
    epp_file_suspects,
    edr_malop,
    edr_machines,
    edr_users,
    edr_suspicions,
):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/mmng/v2/malops",
        status_code=200,
        json={"data": {"data": [EPP_MALOP, EDR_MALOP]}},
    )
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/detection/details",
        status_code=200,
        json=EPP_MALOP_DETAIL,
    )
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/crimes/unified",
        status_code=200,
        json=EDR_MALOP_SUSPICIONS_RESULTS,
    )

    # assert the from_date property is the minute before the faked time
    assert trigger.from_date == (fake_time - 60) * 1000
    # assert we got the last events
    events = list(trigger.fetch_last_events())
    assert len(events) == 9

    # extract events
    assert [epp_malop_detail] + epp_users + epp_machines + epp_file_suspects + [
        edr_malop
    ] + edr_users + edr_machines + edr_suspicions == events

    # assert the from_date property was updated with the most recent seen date
    assert trigger.from_date == EDR_MALOP["lastUpdateTime"] + 1


def test_next_batch_sleep_until_next_batch(trigger, mock_cybereason_api):
    with patch("cybereason_modules.connector_pull_events.time") as mock_time:
        mock_cybereason_api.post(
            "https://fake.cybereason.net/rest/mmng/v2/malops",
            status_code=200,
            json={"data": {"data": [EPP_MALOP] * 16 + [EDR_MALOP] * 18}},
        )
        mock_cybereason_api.post(
            "https://fake.cybereason.net/rest/detection/details",
            status_code=200,
            json=EPP_MALOP_DETAIL,
        )
        mock_cybereason_api.post(
            "https://fake.cybereason.net/rest/crimes/unified",
            status_code=200,
            json=EDR_MALOP_SUSPICIONS_RESULTS,
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, start_time, start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, mock_cybereason_api):
    with patch("cybereason_modules.connector_pull_events.time") as mock_time:
        mock_cybereason_api.post(
            "https://fake.cybereason.net/rest/mmng/v2/malops",
            status_code=200,
            json={"data": {"data": [EPP_MALOP] * 16 + [EDR_MALOP] * 18}},
        )
        mock_cybereason_api.post(
            "https://fake.cybereason.net/rest/detection/details",
            status_code=200,
            json=EPP_MALOP_DETAIL,
        )
        mock_cybereason_api.post(
            "https://fake.cybereason.net/rest/crimes/unified",
            status_code=200,
            json=EDR_MALOP_SUSPICIONS_RESULTS,
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, start_time, start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_failing_authentication(trigger):
    with requests_mock.Mocker() as mock:
        jar = requests_mock.CookieJar()
        jar.set("JSESSIONID", "session_id", domain="fake.cybereason.net")
        mock.post("https://fake.cybereason.net/login.html", status_code=200, cookies=jar, content=LOGIN_HTML)

        with pytest.raises(LoginFailureError):
            trigger.next_batch()


def test_next_batch_with_login_page_as_malops_listing_reponse(trigger, mock_cybereason_api):
    mock_cybereason_api.post(
        "https://fake.cybereason.net/rest/mmng/v2/malops",
        status_code=200,
        content=LOGIN_HTML,
    )

    with pytest.raises(LoginFailureError):
        trigger.next_batch()
