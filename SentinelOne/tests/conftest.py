import random
import uuid
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import Mock

import pytest
from management.mgmtsdk_v2.entities.activity import Activity
from management.mgmtsdk_v2.entities.threat import Threat
from sekoia_automation import constants

from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule
from sentinelone_module.logs.configuration import SentinelOneLogsConnectorConfiguration
from sentinelone_module.logs.connector import (
    SentinelOneActivityLogsConsumer,
    SentinelOneLogsConnector,
    SentinelOneThreatLogsConsumer,
)


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture(scope="session")
def sentinelone_hostname():
    return "abcdef.sentinelone.net"


@pytest.fixture(scope="session")
def sentinelone_module(sentinelone_hostname):
    module = SentinelOneModule()
    module.configuration = {"hostname": sentinelone_hostname, "api_token": "1234567890"}
    return module


@pytest.fixture
def connector(symphony_storage, sentinelone_module):
    connector = SentinelOneLogsConnector(module=sentinelone_module, data_path=symphony_storage)
    connector.configuration = {"intake_key": "intake_key", "frequency": 60}

    connector.log = Mock()
    connector.push_events_to_intakes = Mock(return_value=[])

    yield connector


@pytest.fixture
def activity_1():
    activity = Activity()
    activity.accountId = "12345654789"
    activity.accountName = "SERVICES NETWORK SECURITY (SNS France)"
    activity.activityType = 5020
    activity.agentId = None
    activity.agentUpdatedVersion = None
    activity.comments = None
    activity.createdAt = "2021-03-09T13:03:22.026416Z"
    activity.description = "<ManagementUser with id=, email='foo@bar.fr', user_scope='account'>"
    activity.groupId = None
    activity.groupName = None
    activity.hash = None
    activity.id = str(random.randint(0, 1000000))
    activity.osFamily = None
    activity.primaryDescription = "The management user Support SNS created Sekoia.io site."
    activity.secondaryDescription = None
    activity.siteId = "12345654789"
    activity.siteName = "Sekoia.io"
    activity.threatId = None
    activity.updatedAt = "2021-03-09T13:03:22.021752Z"
    activity.userId = "12345654789"
    yield activity


@pytest.fixture
def activity_2():
    activity = Activity()
    activity.accountId = "12345654789"
    activity.accountName = "SERVICES NETWORK SECURITY (SNS France)"
    activity.activityType = 23
    activity.agentId = None
    activity.agentUpdatedVersion = None
    activity.comments = None
    activity.createdAt = "2021-03-09T15:41:54.448862Z"
    activity.description = "<ManagementUser with id=, email='foo@bar.fr', user_scope='account'>"
    activity.groupId = None
    activity.groupName = None
    activity.hash = None
    activity.id = str(random.randint(0, 1000000))
    activity.osFamily = None
    activity.primaryDescription = "The management user Support SNS added user as Admin."
    activity.secondaryDescription = None
    activity.siteId = "12345654789"
    activity.siteName = "Sekoia.io"
    activity.threatId = None
    activity.updatedAt = "2021-03-09T15:41:54.425005Z"
    activity.userId = "12345654789"
    yield activity


@pytest.fixture
def threat_1():
    threat = dict(
        createdAt="2021-03-09T13:03:22.026416Z",
        id=(str(random.randint(0, 1000000)),),
    )
    yield threat


@pytest.fixture
def threat_2():
    threat = dict(
        createdAt="2021-03-09T15:41:54.448862Z",
        id=(str(random.randint(0, 1000000)),),
    )
    yield threat


@pytest.fixture
def activity_consumer(connector):
    consumer = SentinelOneActivityLogsConsumer(connector)
    consumer.management_client = Mock()
    consumer.start = Mock()
    consumer.is_alive = Mock(return_value=False)

    yield consumer


@pytest.fixture
def threat_consumer(connector):
    consumer = SentinelOneThreatLogsConsumer(connector)
    consumer.management_client = Mock()
    consumer.start = Mock()
    consumer.is_alive = Mock(return_value=False)

    yield consumer
