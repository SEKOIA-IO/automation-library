"""Shared description of the errors of the Sophos APIs, for the messages shown to the users.

The messages are stable: no request, correlation or query ids, so the SDK deduplicates identical errors.
"""

from typing import Any

import requests

# Sophos API, recognized from the request URL -> role required by the API credential
REQUIRED_ROLES: list[tuple[str, str, str]] = [
    # (URL fragment, API name, required role)
    ("id.sophos.com", "authentication", ""),
    ("/whoami/", "authentication", ""),
    ("/siem/", "SIEM API", "Service Principal ReadOnly"),
    ("/xdr-query/", "XDR Data Lake API", "Service Principal Forensics"),
    ("/graphql", "Sophos Fusion GraphQL API", "Service Principal ReadOnly"),
    ("/endpoint/", "Endpoint API", "Service Principal Management"),
    ("/common/", "Common API", "Service Principal ReadOnly"),
]

# 401 and 403 need an action of the customer (credentials, role, licence): they are not transient
CONFIGURATION_ERROR_STATUSES = frozenset({401, 403})


def identify_api(url: str | None) -> tuple[str, str]:
    """Return the name of the Sophos API called by this URL, and the role its credential needs."""
    for fragment, name, role in REQUIRED_ROLES:
        if url and fragment in url:
            return name, role
    return "Sophos API", ""


def describe_error(response: requests.Response) -> str:
    """Stable summary of a Sophos error response, without request or correlation ids."""
    try:
        payload: Any = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict) and (payload.get("error") or payload.get("message")):
        return f"{payload.get('error')}: {payload.get('message')}"

    return str(response.reason or "no details")


def error_hint(status_code: int, url: str | None) -> str:
    """What the user can do about this error, if anything."""
    name, role = identify_api(url)
    if status_code == 401:
        return ". Check the client_id and client_secret of the module, and that the API credential has not expired"
    if status_code == 403:
        hint = f". Check that the API credential has the '{role}' role" if role else ". Check the API credential"
        if name == "XDR Data Lake API":
            hint += " and that the XDR licence of the tenant is valid"
        return hint
    if status_code == 429:
        return ". The Sophos rate limit is reached, try again later"
    if status_code >= 500:
        return ". Error on the Sophos side, try again later"
    return ""


def is_configuration_error(status_code: int | None) -> bool:
    return status_code in CONFIGURATION_ERROR_STATUSES


def support_ids(response: requests.Response) -> str:
    """Request and correlation ids of a Sophos error, for a one-off message (an action), e.g. ' (requestId=...)'."""
    try:
        payload: Any = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    ids = [f"{key}={payload[key]}" for key in ("requestId", "correlationId") if payload.get(key)]
    return f" ({', '.join(ids)})" if ids else ""


def format_http_error(action: str, response: requests.Response) -> str:
    """e.g. 'Failed to fetch the events: status 403 - UNAUTHORIZED_ACCESS: Forbidden. Check that ...'"""
    return (
        f"{action}: status {response.status_code} - {describe_error(response)}"
        f"{error_hint(response.status_code, response.url)}"
    )
