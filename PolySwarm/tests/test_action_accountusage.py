from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.action_polyswarm_accountusage import AccountUsage


@pytest.fixture
def action(data_storage: str, module: PolyswarmModule) -> AccountUsage:
    return AccountUsage(module=module, data_path=data_storage)


def _make_whois(
    *,
    account_name: str = "Acme SOC",
    account_number: int = 4211,
    account_type: str = "team",
    communities: list | None = None,
    tenant: str | None = "acme",
) -> MagicMock:
    whois = MagicMock()
    whois.account_name = account_name
    whois.account_number = account_number
    whois.account_type = account_type
    whois.communities = communities if communities is not None else ["default", "gamma"]
    whois.tenant = tenant
    return whois


def _make_features(
    *,
    plan_name: str = "Enterprise",
    daily_api_limit: int | None = 20000,
    daily_api_remaining: int | None = 17431,
    features: list | None = None,
) -> MagicMock:
    account = MagicMock()
    account.account_number = 4211
    account.account_plan_name = plan_name
    account.plan_period_start = "2026-09-01T00:00:00Z"
    account.plan_period_end = "2026-10-01T00:00:00Z"
    account.window_start = "2026-09-01T00:00:00Z"
    account.window_end = "2026-10-01T00:00:00Z"
    account.tenant = "acme"
    account.daily_api_limit = daily_api_limit
    account.daily_api_remaining = daily_api_remaining
    account.has_stream_access = True
    account.is_trial = False
    account.is_trial_expired = False
    account.features = (
        features
        if features is not None
        else [
            {
                "name": "Scans",
                "tag": "scans",
                "base_uses": 50000,
                "remaining_uses": 42117,
                "value": 50000,
                "overage": 0,
            },
            {
                "name": "Sandbox Detonations",
                "tag": "sandbox",
                "base_uses": 500,
                "remaining_uses": 0,
                "value": 500,
                "overage": 12,
            },
            {
                "name": "Hunting",
                "tag": "hunting",
                "base_uses": None,
                "remaining_uses": None,
                "value": True,
                "overage": None,
            },
        ]
    )
    return account


def _request_exception(status_code: int) -> ps_exceptions.RequestException:
    request = MagicMock()
    request.status_code = status_code
    return ps_exceptions.RequestException(request, "rejected")


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_account_usage_reports_plan_and_quota(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features()

    response = action.run({})
    assert response is not None

    mock_build_client.assert_called_once_with(action.module.configuration)
    assert response["account_name"] == "Acme SOC"
    assert response["account_number"] == "4211"
    assert response["account_type"] == "team"
    assert response["tenant"] == "acme"
    assert response["communities"] == ["default", "gamma"]
    assert response["plan_name"] == "Enterprise"
    assert response["plan_period_end"] == "2026-10-01T00:00:00Z"
    assert response["is_trial"] is False
    assert response["has_stream_access"] is True
    assert response["daily_api_limit"] == 20000
    assert response["daily_api_remaining"] == 17431

    assert [f["name"] for f in response["features"]] == ["Scans", "Sandbox Detonations", "Hunting"]
    assert response["features"][0]["remaining_uses"] == 42117
    assert response["features"][1]["overage"] == 12
    # A feature the plan carries but does not meter by count reports no numbers
    # rather than a zero, which would read as exhausted.
    assert response["features"][2]["base_uses"] is None
    assert response["features"][2]["remaining_uses"] is None

    assert response["exhausted_features"] == ["Sandbox Detonations"]


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_account_usage_never_returns_the_api_key(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features()

    response = action.run({})

    assert "test-api-key" not in str(response)
    assert "apikey" not in response


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_auth_failure_returns_an_actionable_error(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.side_effect = _request_exception(401)

    response = action.run({})

    assert response is None
    assert "rejected the configured API key" in action.error_message
    # The client echoes the whole request back in its exception text, so the
    # message is written here rather than quoted from the exception.
    assert "test-api-key" not in action.error_message
    api.account_features.assert_not_called()


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_usage_limit_failure_says_so(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.side_effect = ps_exceptions.UsageLimitsExceededException(MagicMock(), "429")

    response = action.run({})

    assert response is None
    assert "over its usage limit" in action.error_message


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_missing_plan_still_reports_the_identity(mock_build_client: MagicMock, action: AccountUsage) -> None:
    """Knowing which account the key belongs to is worth returning on its own."""
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.side_effect = ps_exceptions.NotFoundException(MagicMock(), "404")

    response = action.run({})
    assert response is not None

    assert action.error_message is None
    assert response["account_name"] == "Acme SOC"
    assert response["plan_name"] == ""
    assert response["features"] == []
    assert response["exhausted_features"] == []


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_community_objects_are_normalised(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois(communities=[{"name": "default"}, {"slug": "gamma"}])
    api.account_features.return_value = _make_features()

    response = action.run({})

    assert response["communities"] == ["default", "gamma"]


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_trial_account_is_flagged(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois(account_type="user", tenant=None)
    account = _make_features(plan_name="Community", daily_api_limit=250, daily_api_remaining=0)
    account.tenant = None
    account.is_trial = True
    account.is_trial_expired = True
    account.has_stream_access = False
    api.account_features.return_value = account

    response = action.run({})

    assert response["plan_name"] == "Community"
    assert response["is_trial"] is True
    assert response["is_trial_expired"] is True
    assert response["has_stream_access"] is False
    assert response["daily_api_remaining"] == 0
    assert response["tenant"] == ""


# --- the metered quota path ---
#
# The account this action was built against carries only on/off entitlements,
# so a feature with a real remaining count, and the unlimited (-1) allowance
# the platform reports for a feature with no cap, had never run against real
# data. These tests exercise that branch directly.


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_metered_feature_with_uses_left_is_not_exhausted(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features(
        features=[
            {
                "name": "Hunts",
                "tag": "hunts",
                "base_uses": 1000,
                "remaining_uses": 217,
                "value": 1000,
                "overage": 0,
            }
        ]
    )

    response = action.run({})

    feature = response["features"][0]
    assert feature["kind"] == "metered"
    assert feature["enabled"] is None
    assert feature["unlimited"] is False
    assert feature["remaining_uses"] == 217
    assert response["exhausted_features"] == []


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_metered_feature_at_zero_is_genuinely_exhausted(mock_build_client: MagicMock, action: AccountUsage) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features(
        features=[
            {
                "name": "Hunts",
                "tag": "hunts",
                "base_uses": 1000,
                "remaining_uses": 0,
                "value": 1000,
                "overage": 5,
            }
        ]
    )

    response = action.run({})

    feature = response["features"][0]
    assert feature["kind"] == "metered"
    assert feature["unlimited"] is False
    assert feature["remaining_uses"] == 0
    assert response["exhausted_features"] == ["Hunts"]


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_unlimited_metered_feature_is_never_exhausted(mock_build_client: MagicMock, action: AccountUsage) -> None:
    """The platform reports an unmetered allowance as -1 on remaining_uses."""
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features(
        features=[
            {
                "name": "Scans",
                "tag": "scans",
                "base_uses": -1,
                "remaining_uses": -1,
                "value": 999999,
                "overage": None,
            }
        ]
    )

    response = action.run({})

    feature = response["features"][0]
    assert feature["kind"] == "metered"
    assert feature["unlimited"] is True
    # exhausted_features must never fire on an unlimited feature, no matter
    # that remaining_uses is a negative number.
    assert response["exhausted_features"] == []


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_boolean_entitlement_never_counts_as_exhausted_even_at_zero_counters(
    mock_build_client: MagicMock, action: AccountUsage
) -> None:
    """A switched-on feature's use counters are zero and mean nothing: never exhausted."""
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features(
        features=[
            {
                "name": "Hunting",
                "tag": "hunting",
                "base_uses": 0,
                "remaining_uses": 0,
                "value": True,
                "overage": None,
            }
        ]
    )

    response = action.run({})

    feature = response["features"][0]
    assert feature["kind"] == "boolean"
    assert feature["enabled"] is True
    assert response["exhausted_features"] == []


@patch("polyswarm_modules.action_polyswarm_accountusage.build_client")
def test_mixed_boolean_and_metered_features_are_reported_independently(
    mock_build_client: MagicMock, action: AccountUsage
) -> None:
    api = mock_build_client.return_value
    api.account_whois.return_value = _make_whois()
    api.account_features.return_value = _make_features(
        features=[
            {"name": "API Access", "tag": "api", "base_uses": None, "remaining_uses": None, "value": True},
            {"name": "Hunts", "tag": "hunts", "base_uses": 100, "remaining_uses": 0, "value": 100, "overage": 0},
            {
                "name": "Sandbox",
                "tag": "sandbox",
                "base_uses": -1,
                "remaining_uses": -1,
                "value": -1,
                "overage": None,
            },
        ]
    )

    response = action.run({})

    by_name = {f["name"]: f for f in response["features"]}
    assert by_name["API Access"]["kind"] == "boolean"
    assert by_name["Hunts"]["kind"] == "metered"
    assert by_name["Hunts"]["unlimited"] is False
    assert by_name["Sandbox"]["kind"] == "metered"
    assert by_name["Sandbox"]["unlimited"] is True
    assert response["exhausted_features"] == ["Hunts"]
