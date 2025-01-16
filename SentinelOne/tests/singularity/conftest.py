import pytest

from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule


@pytest.fixture
def sentinel_module() -> SentinelOneModule:
    """
    Create a SentinelOne module.

    Args:
        symphony_storage: Path
    """
    module = SentinelOneModule()
    module.configuration = SentinelOneConfiguration(
        api_token="test_token",
        hostname="http://testhost",
    )

    return module
