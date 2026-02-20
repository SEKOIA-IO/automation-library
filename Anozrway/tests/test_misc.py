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
    cfg = AnozrwayModuleConfiguration(
        anozrway_client_id="cid",
        anozrway_client_secret="secret",
    )
    assert cfg.anozrway_base_url == "https://balise.anozrway.com"
    assert cfg.timeout_seconds == 30


def test_metrics_smoke():
    # symphony_module_common counters: _name without namespace prefix
    assert events_collected._name == "symphony_module_common_collected_messages"
    assert events_forwarded._name == "symphony_module_common_forwarded_events"
    assert events_duplicated._name == "symphony_module_common_duplicated_events"
    assert api_request_duration._name == "symphony_module_common_forward_events_duration"
    assert checkpoint_age._name == "symphony_module_common_events_lags"
    # module-specific
    assert api_requests._name == "symphony_module_anozrway_api_requests"
