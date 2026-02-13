from anozrway_modules import AnozrwayModule
from anozrway_modules.client.errors import AnozrwayAuthError, AnozrwayError, AnozrwayRateLimitError
from anozrway_modules.metrics import (
    api_request_duration,
    api_requests,
    checkpoint_age,
    events_collected,
    events_duplicated,
    events_forwarded,
)
from anozrway_modules.models import AnozrwayModuleConfiguration


def test_module_metadata():
    module = AnozrwayModule()
    assert module.name == "Anozrway"
    assert "Anozrway" in module.description


def test_error_classes():
    assert issubclass(AnozrwayAuthError, AnozrwayError)
    assert issubclass(AnozrwayRateLimitError, AnozrwayError)


def test_models_smoke():
    assert AnozrwayModuleConfiguration() is not None


def test_metrics_smoke():
    assert events_collected._name == "anozrway_historical_events_collected"
    assert events_forwarded._name == "anozrway_historical_events_forwarded"
    assert events_duplicated._name == "anozrway_historical_events_duplicated"
    assert api_requests._name == "anozrway_api_requests"
    assert api_request_duration._name == "anozrway_api_request_duration_seconds"
    assert checkpoint_age._name == "anozrway_checkpoint_age_seconds"
