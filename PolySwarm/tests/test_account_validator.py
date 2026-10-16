from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions
from requests import ConnectionError as RequestsConnectionError
from requests import Response
from requests.exceptions import HTTPError, ReadTimeout

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.account_validator import PolyswarmAccountValidator
from tests.helpers import autospec_build_client, autospec_request

TARGET = "polyswarm_modules.account_validator.build_client"
KEY_ECHO = "test-api-key was rejected by https://api.polyswarm.network/v3"


@pytest.fixture
def validator(data_storage: str, module: PolyswarmModule) -> PolyswarmAccountValidator:
    return PolyswarmAccountValidator(module=module, data_path=data_storage)


def _logged(validator: PolyswarmAccountValidator) -> list[tuple[str, str]]:
    return [(call.args[0], call.kwargs.get("level", "debug")) for call in validator.log.call_args_list]


def _response(status: int) -> Response:
    response = Response()
    response.status_code = status
    return response


@patch(TARGET, new_callable=autospec_build_client)
def test_a_working_key_is_accepted(mock_build_client: MagicMock, validator: PolyswarmAccountValidator) -> None:
    mock_build_client.return_value.account_whois.return_value = MagicMock()

    assert validator.validate() is True
    assert validator._error is None


@patch(TARGET, new_callable=autospec_build_client)
def test_no_account_is_refused_and_logged(mock_build_client: MagicMock, validator: PolyswarmAccountValidator) -> None:
    mock_build_client.return_value.account_whois.return_value = None

    with patch.object(validator, "log"):
        assert validator.validate() is False
        logged = _logged(validator)

    assert validator._error is not None
    assert "no account" in validator._error
    assert (validator._error, "error") in logged


@pytest.mark.parametrize("status", [401, 403])
@patch(TARGET, new_callable=autospec_build_client)
def test_a_rejected_key_is_refused_and_says_so(
    mock_build_client: MagicMock, validator: PolyswarmAccountValidator, status: int
) -> None:
    mock_build_client.return_value.account_whois.side_effect = ps_exceptions.RequestException(
        autospec_request(status), KEY_ECHO
    )

    with patch.object(validator, "log"):
        assert validator.validate() is False
        logged = _logged(validator)

    assert validator._error is not None
    assert "rejected the configured API key" in validator._error
    assert f"HTTP {status}" in validator._error
    assert "test-api-key" not in validator._error
    assert (validator._error, "error") in logged


@patch(TARGET, new_callable=autospec_build_client)
def test_a_rejection_reported_by_the_transport_layer_is_also_a_rejected_key(
    mock_build_client: MagicMock, validator: PolyswarmAccountValidator
) -> None:
    mock_build_client.return_value.account_whois.side_effect = HTTPError(KEY_ECHO, response=_response(401))

    assert validator.validate() is False
    assert "rejected the configured API key" in validator._error


@patch(TARGET, new_callable=autospec_build_client)
def test_a_spent_quota_does_not_refuse_a_valid_key(
    mock_build_client: MagicMock, validator: PolyswarmAccountValidator
) -> None:
    mock_build_client.return_value.account_whois.side_effect = ps_exceptions.UsageLimitsExceededException(
        autospec_request(429), KEY_ECHO
    )

    with patch.object(validator, "log"):
        assert validator.validate() is True
        logged = _logged(validator)

    assert validator._error is None
    assert any(level == "warning" and "usage limit" in message for message, level in logged)
    assert all("test-api-key" not in message for message, _ in logged)


@pytest.mark.parametrize(
    "failure",
    [
        RequestsConnectionError(KEY_ECHO),
        ReadTimeout(KEY_ECHO),
        HTTPError(KEY_ECHO, response=_response(502)),
        ps_exceptions.RequestException(autospec_request(503), KEY_ECHO),
        ps_exceptions.InvalidJSONResponseException(KEY_ECHO),
    ],
)
@patch(TARGET, new_callable=autospec_build_client)
def test_an_outage_is_not_reported_as_a_rejected_key(
    mock_build_client: MagicMock, validator: PolyswarmAccountValidator, failure: Exception
) -> None:
    mock_build_client.return_value.account_whois.side_effect = failure

    with patch.object(validator, "log"):
        assert validator.validate() is False
        logged = _logged(validator)

    assert validator._error is not None
    assert "rejected" not in validator._error.replace("has not been rejected", "")
    assert "could not be reached" in validator._error
    assert "test-api-key" not in validator._error
    assert (validator._error, "error") in logged


@patch(TARGET, new_callable=autospec_build_client)
def test_a_missing_result_means_no_account(mock_build_client: MagicMock, validator: PolyswarmAccountValidator) -> None:
    mock_build_client.return_value.account_whois.side_effect = ps_exceptions.NoResultsException(
        autospec_request(204), "none"
    )

    assert validator.validate() is False
    assert "no account" in validator._error


@patch(TARGET, new_callable=autospec_build_client)
def test_every_error_is_sent_back_with_the_result(
    mock_build_client: MagicMock, validator: PolyswarmAccountValidator
) -> None:
    mock_build_client.return_value.account_whois.side_effect = ps_exceptions.RequestException(
        autospec_request(401), KEY_ECHO
    )

    with patch.object(validator, "_send_request") as send:
        validator.send_results(validator.validate())

    payload = send.call_args.args[0]
    assert payload["results"] == {"success": False}
    assert "rejected the configured API key" in payload["error"]
