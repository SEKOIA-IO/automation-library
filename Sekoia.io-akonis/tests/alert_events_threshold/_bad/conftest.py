import pytest
import aiohttp
import asyncio
from sekoiaio.triggers.alert_events_threshold import AlertEventsThresholdTrigger


# ------------------------------------------------------------------------------
# GLOBAL AIOHTTP SESSION (shared by all tests)
# ------------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def aiohttp_session():
    async with aiohttp.ClientSession() as session:
        yield session


# ------------------------------------------------------------------------------
# ARESPONSES SERVER
# ------------------------------------------------------------------------------

@pytest.fixture
async def aresp(aresponses):
    """
    Wrapper around aresponses to ensure consistent configuration across tests.
    """
    # Allow passthrough for localhost and actual internet if needed
    aresponses.allow_passthrough = True
    yield aresponses


# ------------------------------------------------------------------------------
# CENTRAL TRIGGER FIXTURE (used by all tests)
# ------------------------------------------------------------------------------
#
# This fixture:
#   ✔ Creates a trigger
#   ✔ Injects the aiohttp session
#   ✔ Overrides read-only alert_api_url & event_count_api_url using monkeypatch
#   ✔ Makes URLs unique per test using a dummy host name for aresponses
# ------------------------------------------------------------------------------

@pytest.fixture
async def trigger(monkeypatch, aiohttp_session):
    """
    Create a fully functional AlertEventsThresholdTrigger with:
      - Patched alert_api_url
      - Patched event_count_api_url
      - Real aiohttp session
    This makes all aresponses tests uniform, stable, and clean.
    """
    t = AlertEventsThresholdTrigger()

    # Inject session (the trigger normally creates its own)
    t.session = aiohttp_session

    # Base test URLs (aresponses will intercept)
    MOCK_ALERT_API = "http://alert-api.test"
    MOCK_EVENT_COUNT_API = "http://event-count.test"

    # Patch read-only @property attributes on the class
    monkeypatch.setattr(
        t.__class__,
        "alert_api_url",
        property(lambda self: MOCK_ALERT_API)
    )
    monkeypatch.setattr(
        t.__class__,
        "event_count_api_url",
        property(lambda self: MOCK_EVENT_COUNT_API)
    )
    monkeypatch.setattr(
        t.__class__,
        "event_api_url",
        property(lambda self: MOCK_EVENT_COUNT_API)
    )

    # Important: trigger internals sometimes use asyncio.sleep → patch in tests
    monkeypatch.setattr(asyncio, "sleep", asyncio.sleep)

    return t


# ------------------------------------------------------------------------------
# Utility helper for JSON responses
# ------------------------------------------------------------------------------

@pytest.fixture
def json_response():
    """
    Convenient helper to create JSON responses in aresponses using dicts.
    """

    def _json(data, status=200, headers=None):
        headers = headers or {"Content-Type": "application/json"}
        import json

        return status, headers, json.dumps(data)

    return _json
