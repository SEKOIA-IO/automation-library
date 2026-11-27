import json
from unittest.mock import Mock

import pytest
import requests
import urllib3
from pydantic import ValidationError
from sekoia_automation.connector import DefaultConnectorConfiguration

from sophos_module.base import SophosConfiguration, SophosConnector, SophosModule
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.exceptions import SophosApiAuthenticationError

CONFIGURATION = {
    "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
    "api_host": "https://api.central.sophos.com",
    "client_id": "my-id",
    "client_secret": "my-password",
}


def test_configuration_defaults_graphql_api_url():
    # module configurations created before the Fusion connector have no graphql_api_url
    assert SophosConfiguration(**CONFIGURATION).graphql_api_url == "https://api.taegis.sophos.com"


def test_configuration_custom_graphql_api_url():
    configuration = SophosConfiguration(**CONFIGURATION, graphql_api_url="https://graphql.example.com")
    assert configuration.graphql_api_url == "https://graphql.example.com"


@pytest.mark.parametrize("missing", ["oauth2_authorization_url", "api_host", "client_id", "client_secret"])
def test_configuration_required_fields(missing):
    with pytest.raises(ValidationError):
        SophosConfiguration(**{key: value for key, value in CONFIGURATION.items() if key != missing})


def test_client_secret_is_secret():
    schema = SophosConfiguration.model_json_schema()
    assert schema["properties"]["client_secret"]["secret"] is True


# --------------------------------------------------------------------------- SophosConnector


class DummyConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60


class DummyConnector(SophosConnector):
    configuration: DummyConfiguration
    name = "Dummy trigger"
    collect_error_action = "Failed to collect"

    def collect(self) -> None:
        pass


def http_error(status_code: int, url: str = "https://api-eu01.central.sophos.com/siem/v1/events", body=None):
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Reason"
    response.url = url
    response._content = json.dumps(body or {"requestId": "r-1"}).encode()
    return requests.HTTPError(f"{status_code} error for url {url}", response=response)


@pytest.fixture
def connector(symphony_storage):
    connector = DummyConnector(module=SophosModule(), data_path=symphony_storage)
    connector.module.configuration = {**CONFIGURATION, "graphql_api_url": "https://graphql.example.com"}
    connector.configuration = {"intake_key": "0123456789", "frequency": 60}
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.authentication = Mock()
    return connector


def run_cycles(connector, *outcomes):
    """Run the loop for len(outcomes) cycles; each outcome is None or the exception raised by collect()."""
    remaining = list(outcomes)

    def collect():
        outcome = remaining.pop(0)
        if not remaining:
            connector._stop_event.set()
        if outcome is not None:
            raise outcome

    connector.collect = Mock(side_effect=collect)
    connector.run()


def user_messages(connector) -> list[tuple[str, str]]:
    return [(call.kwargs["level"], call.kwargs["message"]) for call in connector.log.call_args_list]


def test_authentication_and_client(symphony_storage):
    connector = DummyConnector(module=SophosModule(), data_path=symphony_storage)
    connector.module.configuration = {**CONFIGURATION, "graphql_api_url": "https://graphql.example.com/"}

    assert isinstance(connector.authentication, SophosApiAuthentication)
    assert connector.client.auth is connector.authentication
    assert connector.client.graphql_api_url == "https://graphql.example.com"


def test_base_hooks(connector):
    with pytest.raises(NotImplementedError):
        SophosConnector.collect(connector)
    assert SophosConnector.before_collect(connector) is None


@pytest.mark.parametrize("frequency, expected_sleeps", [(60, [60]), (0, [])])
def test_run_cycle(connector, no_sleep, frequency, expected_sleeps):
    connector.configuration.frequency = frequency
    connector.before_collect = Mock()

    run_cycles(connector, None)

    connector.authentication.get_credentials.assert_called_once()
    connector.before_collect.assert_called_once()
    assert no_sleep == expected_sleeps
    assert user_messages(connector) == [("info", "Dummy trigger has started"), ("info", "Dummy trigger has stopped")]


@pytest.mark.parametrize(
    "error, expected_message",
    [
        pytest.param(
            http_error(503),
            "Failed to collect: status 503 - Reason. Error on the Sophos side, try again later",
            id="http-error-with-response",
        ),
        pytest.param(
            requests.HTTPError("no response"), "Failed to collect: HTTPError", id="http-error-without-response"
        ),
        pytest.param(requests.ConnectionError("unreachable"), "Failed to collect: ConnectionError", id="network"),
        pytest.param(requests.Timeout("slow"), "Failed to collect: Timeout", id="timeout"),
        pytest.param(urllib3.exceptions.HTTPError("urllib3"), "Failed to collect: HTTPError", id="urllib3"),
    ],
)
def test_run_recoverable_errors(connector, error, expected_message):
    run_cycles(connector, error, None)

    assert connector.collect.call_count == 2
    assert user_messages(connector)[1:-1] == [("error", expected_message)]
    connector.log_exception.assert_not_called()


def test_run_configuration_errors_are_shown_once_per_period(connector):
    access_refused = http_error(403, body={"error": "UNAUTHORIZED_ACCESS", "message": "Forbidden"})

    run_cycles(connector, access_refused, access_refused, access_refused)

    assert user_messages(connector)[1:-1] == [
        (
            "error",
            "Failed to collect: status 403 - UNAUTHORIZED_ACCESS: Forbidden"
            ". Check that the API credential has the 'Service Principal ReadOnly' role",
        )
    ]


def test_configuration_error_shown_again_after_the_period(connector):
    connector.log_error("Access refused", configuration_error=True)
    connector._error_logged_at["Access refused"] -= SophosConnector.configuration_error_log_period
    connector.log_error("Access refused", configuration_error=True)

    assert user_messages(connector) == [("error", "Access refused"), ("error", "Access refused")]


def test_other_errors_are_not_throttled(connector):
    connector.log_error("Sophos is down")
    connector.log_error("Sophos is down")

    # deduplicated by the SDK within 60 seconds only
    assert user_messages(connector) == [("error", "Sophos is down"), ("error", "Sophos is down")]


def test_run_raises_unexpected_errors(connector):
    with pytest.raises(ValueError):
        run_cycles(connector, ValueError("boom"))

    connector.log_exception.assert_called_once()
    assert user_messages(connector)[-1] == ("info", "Dummy trigger has stopped")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(requests.ConnectionError("unreachable"), id="network"),
        pytest.param(http_error(503, url="https://id.sophos.com/api/v2/oauth2/token"), id="server-error"),
    ],
)
def test_run_retries_a_temporary_authentication_failure_at_startup(connector, error):
    connector.authentication.get_credentials.side_effect = [error, None]

    run_cycles(connector, None)

    assert connector.authentication.get_credentials.call_count == 2
    connector.collect.assert_called_once()
    messages = user_messages(connector)
    assert messages[0] == ("info", "Dummy trigger has started")
    assert messages[1][0] == "error" and messages[1][1].startswith("Failed to collect:")
    assert messages[-1] == ("info", "Dummy trigger has stopped")
    connector.log_exception.assert_not_called()


@pytest.mark.parametrize("during_cycle", [False, True], ids=["at-startup", "during-a-cycle"])
def test_run_stops_on_authentication_error(connector, during_cycle):
    error = SophosApiAuthenticationError("bad credentials")
    if during_cycle:
        run_cycles(connector, error)
    else:
        connector.authentication.get_credentials.side_effect = error
        connector.run()

    connector.log_exception.assert_not_called()
    assert user_messages(connector) == [
        ("info", "Dummy trigger has started"),
        ("critical", "bad credentials"),
        ("info", "Dummy trigger has stopped"),
    ]
