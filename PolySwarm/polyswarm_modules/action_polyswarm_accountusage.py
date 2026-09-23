from typing import Any

from polyswarm_api import exceptions as ps_exceptions
from pydantic import BaseModel, Field

from polyswarm_modules.base import PolyswarmAction
from polyswarm_modules.client import build_client

NUMERIC_ERRORS: tuple[type[Exception], ...] = (TypeError, ValueError)

# The account endpoints are the only place the platform states an entitlement,
# so this action exists to answer one question: is the playbook failing because
# the key is wrong, because the plan does not carry the feature, or because the
# quota for the period is spent. None of the answers include the key itself.
CALL_FAILURES = (
    ps_exceptions.NoResultsException,
    ps_exceptions.NotFoundException,
    ps_exceptions.InvalidValueException,
    ps_exceptions.UsageLimitsExceededException,
    ps_exceptions.RequestException,
)


def _as_int(value: Any) -> int | None:
    """Coerce a quota number from the client, or None when it is not a number."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except NUMERIC_ERRORS:
        return None


def _as_text(value: Any) -> str:
    """Render a scalar field as text, with None becoming an empty string."""
    if value is None:
        return ""
    return str(value)


def _as_community_names(values: Any) -> list[str]:
    """Normalise the community list, which is names on the current API and objects on older ones."""
    if not isinstance(values, (list, tuple, set)):
        return []

    names: list[str] = []
    for value in values:
        if isinstance(value, dict):
            raw = value.get("name") or value.get("slug") or ""
        elif isinstance(value, str):
            raw = value
        else:
            continue
        name = raw.strip()
        if name:
            names.append(name)
    return names


class AccountUsageArguments(BaseModel):
    """AccountUsage reads the account behind the configured key, so it takes no arguments."""


class FeatureQuota(BaseModel):
    name: str
    tag: str = ""
    kind: str = ""
    enabled: bool | None = None
    unlimited: bool = False
    base_uses: int | None = None
    remaining_uses: int | None = None
    overage: int | None = None


class AccountUsageResponse(BaseModel):
    account_name: str = ""
    account_number: str = ""
    account_type: str = ""
    tenant: str = ""
    communities: list[str] = Field(default_factory=list)
    plan_name: str = ""
    plan_period_start: str = ""
    plan_period_end: str = ""
    is_trial: bool = False
    is_trial_expired: bool = False
    has_stream_access: bool = False
    daily_api_limit: int | None = None
    daily_api_remaining: int | None = None
    features: list[FeatureQuota] = Field(default_factory=list)
    exhausted_features: list[str] = Field(default_factory=list)


class AccountUsage(PolyswarmAction):
    """Action to answer why a playbook is failing PolySwarm calls.

    Reports the account, plan and remaining quota behind the configured key,
    so an analyst can tell whether the problem is a bad key, a feature the
    plan does not carry, or a spent quota.
    """

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        AccountUsageArguments(**arguments)

        api = build_client(self.module.configuration)

        try:
            whois = api.account_whois()
        except CALL_FAILURES as exc:
            self.error(self._failure_message(exc, "identify the account"))
            return None

        response = AccountUsageResponse(
            account_name=_as_text(getattr(whois, "account_name", "")),
            account_number=_as_text(getattr(whois, "account_number", "")),
            account_type=_as_text(getattr(whois, "account_type", "")),
            tenant=_as_text(getattr(whois, "tenant", "")),
            communities=_as_community_names(getattr(whois, "communities", None)),
        )

        try:
            account = api.account_features()
        except CALL_FAILURES as exc:
            # The identity answer is still worth returning: an analyst chasing a
            # failing playbook needs to know which account the key belongs to
            # even when the plan endpoint is the thing refusing them.
            self.log(
                f"PolySwarm did not return the plan and quota ({type(exc).__name__}), "
                "reporting the account identity only",
                level="info",
            )
            return response.model_dump()

        self._apply_plan(response, account)
        return response.model_dump()

    def _apply_plan(self, response: AccountUsageResponse, account: Any) -> None:
        """Fill the plan and quota fields from the account features resource."""
        response.plan_name = _as_text(getattr(account, "account_plan_name", ""))
        response.plan_period_start = _as_text(getattr(account, "plan_period_start", ""))
        response.plan_period_end = _as_text(getattr(account, "plan_period_end", ""))
        response.is_trial = bool(getattr(account, "is_trial", False))
        response.is_trial_expired = bool(getattr(account, "is_trial_expired", False))
        response.has_stream_access = bool(getattr(account, "has_stream_access", False))
        response.daily_api_limit = _as_int(getattr(account, "daily_api_limit", None))
        response.daily_api_remaining = _as_int(getattr(account, "daily_api_remaining", None))

        if not response.tenant:
            response.tenant = _as_text(getattr(account, "tenant", ""))
        if not response.account_number:
            response.account_number = _as_text(getattr(account, "account_number", ""))

        features = getattr(account, "features", None)
        if not isinstance(features, (list, tuple)):
            return

        # The platform decides what a plan is metered on, so the feature list is
        # reported as it arrives rather than narrowed to a fixed set of names.
        # Scans, hunts and sandbox detonations are entries in this list, not
        # fields of their own.
        for feature in features:
            if not isinstance(feature, dict):
                continue
            name = _as_text(feature.get("name")).strip()
            if not name:
                continue
            # The client drops the platform's "type" field but keeps "value",
            # and its Python type is the discriminator: a bool is an on or off
            # entitlement, a number is a metered allowance.
            raw_value = feature.get("value")
            kind = "boolean" if isinstance(raw_value, bool) else "metered"
            remaining = _as_int(feature.get("remaining_uses"))
            response.features.append(
                FeatureQuota(
                    name=name,
                    tag=_as_text(feature.get("tag")).strip(),
                    kind=kind,
                    # A boolean feature is an entitlement that is on or off. Its
                    # use counters are always zero and mean nothing.
                    enabled=bool(raw_value) if kind == "boolean" else None,
                    # The platform writes an unmetered allowance as -1.
                    unlimited=remaining is not None and remaining < 0,
                    base_uses=_as_int(feature.get("base_uses")),
                    remaining_uses=remaining,
                    overage=_as_int(feature.get("overage")),
                )
            )

        # Only a metered feature can run out. Counting a switched-on entitlement
        # as exhausted, which its zero counters invite, would tell an analyst the
        # whole account is spent when nothing is.
        response.exhausted_features = [
            feature.name
            for feature in response.features
            if feature.kind != "boolean"
            and not feature.unlimited
            and feature.remaining_uses is not None
            and feature.remaining_uses <= 0
        ]

    @staticmethod
    def _failure_message(exc: Exception, attempt: str) -> str:
        """Describe a failed account call without quoting the client, which echoes the request back."""
        status = getattr(getattr(exc, "request", None), "status_code", None)
        if status in (401, 403):
            return (
                f"PolySwarm rejected the configured API key, so it could not {attempt}. "
                "Check the key and the community on the module configuration."
            )
        if status == 429 or isinstance(exc, ps_exceptions.UsageLimitsExceededException):
            return f"PolySwarm reported the account over its usage limit, so it could not {attempt}."
        return f"PolySwarm did not {attempt} ({type(exc).__name__})."
