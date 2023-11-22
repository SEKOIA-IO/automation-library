import pytest
from faker import Faker

from connectors import TrellixModule


@pytest.fixture(scope="session")
def module(session_faker: Faker) -> TrellixModule:
    """
    Generate TrellixModule.

    Args:
        session_faker: Faker

    Returns:
        TrellixModule:
    """
    module = TrellixModule()

    module.configuration = {
        "client_id": session_faker.word(),
        "client_secret": session_faker.word(),
        "api_key": session_faker.word(),
        "delay": session_faker.random.randint(1, 10),
        "ratelimit_per_minute": session_faker.random.randint(1, 10),
        "records_per_request": session_faker.random.randint(1, 100),
        "auth_url": session_faker.uri(),
        "base_url": session_faker.uri(),
    }

    return module
