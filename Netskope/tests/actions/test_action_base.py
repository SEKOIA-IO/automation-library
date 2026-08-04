from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from sekoia_automation.exceptions import ModuleConfigurationError

from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


@pytest.fixture
def base_action(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_api_token_missing_should_raise_explicit_message(base_action):
    with pytest.raises(
        ModuleConfigurationError,
        match="The API token is undefined. Please set it in action arguments",
    ):
        _ = base_action.api_token


def test_api_token_empty_should_raise_explicit_message(base_action):
    base_action.initialize_action_arguments(NetskopeActionArguments(api_token=""))

    with pytest.raises(
        ModuleConfigurationError,
        match="The API token is undefined. Please set it in action arguments",
    ):
        _ = base_action.api_token


def test_normalize_urls_with_empty_items():
    """Test normalize_urls filters out empty and None items."""
    result = NetskopeAction.normalize_urls([None, "", "  ", "valid.com", ""])
    assert result == ["valid.com"]


def test_normalize_urls_deduplicates():
    """Test normalize_urls removes duplicates and preserves order."""
    result = NetskopeAction.normalize_urls(["a.com", "b.com", "a.com"])
    assert result == ["a.com", "b.com"]


def test_normalize_urls_sorts_by_default():
    """Test normalize_urls sorts alphabetically by default."""
    result = NetskopeAction.normalize_urls(["z.com", "a.com", "m.com"])
    assert result == ["a.com", "m.com", "z.com"]


def test_normalize_urls_preserves_order_when_sort_false():
    """Test normalize_urls preserves insertion order when sort_items=False."""
    result = NetskopeAction.normalize_urls(
        ["z.com", "a.com", "m.com"], sort_items=False
    )
    assert result == ["z.com", "a.com", "m.com"]


def test_extract_urls_filters_non_strings():
    """Test extract_urls only returns string URLs, filtering out non-strings."""
    blocklist = {"data": {"urls": ["valid.com", 123, None, "another.com"]}}
    result = NetskopeAction.extract_urls(blocklist)
    assert result == ["valid.com", "another.com"]


def test_extract_urls_with_missing_data():
    """Test extract_urls handles missing data gracefully."""
    result = NetskopeAction.extract_urls({"data": {}})
    assert result == []
    result = NetskopeAction.extract_urls({})
    assert result == []


def test_base_url_with_dict_config(symphony_storage, trigger):
    """Test base_url extracts from dict-style module configuration."""
    # Bypass module validation to exercise the raw dict branch in base_url.
    trigger.module._configuration = {"base_url": "https://dict.example.com"}
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    assert action.base_url == "https://dict.example.com"


def test_base_url_with_object_config(symphony_storage, trigger):
    """Test base_url extracts from object-style module configuration via getattr."""
    trigger.module.configuration = {
        "base_url": "https://object.example.com",
        "api_token": "token",
    }
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    assert action.base_url == "https://object.example.com"


def test_base_url_strips_trailing_slash(symphony_storage, trigger):
    """Test base_url removes trailing slash from URL."""
    trigger.module.configuration = {
        "base_url": "https://example.com/",
        "api_token": "token",
    }
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    assert action.base_url == "https://example.com"


def test_base_url_raises_when_undefined(symphony_storage, trigger):
    """Test base_url raises error when not found in configuration."""
    trigger.module.configuration = {
        "base_url": None
    }  # NULL value should still allow assignment
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)
    with pytest.raises(
        ModuleConfigurationError,
        match="The base url is undefined",
    ):
        _ = action.base_url


def test_base_url_fallback_from_raw_config_on_validation_error(
    symphony_storage, trigger
):
    """Test base_url falls back to raw config file when model validation fails."""
    action = AppendToBlocklistAction(module=trigger.module, data_path=symphony_storage)

    trigger.module.load_config = MagicMock(
        return_value={"base_url": "https://fallback.example.com"}
    )

    with patch.object(
        trigger.module.__class__,
        "configuration",
        new_callable=PropertyMock,
        side_effect=ModuleConfigurationError("config error"),
    ):
        assert action.base_url == "https://fallback.example.com"
        trigger.module.load_config.assert_called_once()
