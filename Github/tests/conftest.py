import asyncio
import random
import time
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any

import pytest
from faker import Faker
from sekoia_automation import constants


@pytest.fixture
def last_timestamp() -> int:
    """
    Get last timestamp.

    Returns:
        int:
    """
    return round(time.time() * 1000) - 60000


@pytest.fixture
def github_response() -> list[dict[str, Any]]:
    """
    Github api mocked response.

    Returns:
        list[dict[str, Any]]:
    """
    return [
        {
            "@timestamp": 1685465626150,
            "_document_id": "aCjok7V1YYqP1c9IE6qbkg",
            "action": "org.block_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465626150,
            "operation_type": "create",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
        {
            "@timestamp": 1685465627991,
            "_document_id": "gMzuZXn3m1ewbOR6RkNnLw",
            "action": "org.unblock_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465627991,
            "operation_type": "remove",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
        {
            "@timestamp": 1685465630880,
            "_document_id": "UKmJTzlW7D2OvZ5F3GrpnA",
            "action": "org.block_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465630880,
            "operation_type": "create",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
        {
            "@timestamp": 1685465633434,
            "_document_id": "Ih4X_g0X7Ots5Mr6O-eozA",
            "action": "org.unblock_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465633434,
            "operation_type": "remove",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
    ]


@pytest.fixture(scope="session")
def faker_locale() -> list[str]:
    """
    Configure Faker to use correct locale.

    Returns:
        List[str]:
    """
    return ["en"]


@pytest.fixture(scope="session")
def faker_seed() -> int:
    """
    Configure Faker to use correct seed.

    Returns:
        int:
    """
    return random.randint(1, 10000)


@pytest.fixture(scope="session")
def session_faker(faker_locale: list[str], faker_seed: int) -> Faker:
    """
    Configure session lvl Faker to use correct seed and locale.

    Args:
        faker_locale: List[str]
        faker_seed: int

    Returns:
        Faker:
    """
    instance = Faker(locale=faker_locale)
    instance.seed_instance(seed=faker_seed)

    return instance


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop

    loop.close()


@pytest.fixture
def pem_content() -> str:
    """
    Get pem content.

    Returns:
        str:
    """
    return """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAtxc7AZKEnNFynjXzIEFl64dcu8X6GfoSsyJOhRwEEyv7dF58
p/dof0E8JSrpxOwOtcNYomDkPA+dRhKsgXKwYfn9oUbpAOXtr+OyPODc4G65JXby
ALGPJQcoK/763mTcwy6S6bldfNk5CVUH3lUIPQd+NKnZl56FcRuXqD/TqO6+kgse
uty3ISZocJo16HhuBsQnQ00bpxzcSo6BMlk2GBM85yPbQVR/+OwJCMat13TnTQYk
TJAm6O6lkKTXXEgk8UtU3/LAf7WgtgE4HdfcPWpDNSnfU87OHSprBWV8ItqE9cPs
09tfC5d+r6ZkE7UK0JzBoQBEn5c7L2ModPByjQIDAQABAoIBABiRW2+Yk4bfa/vi
zV70p5J1NXJU3HyD2+KBpfuiiMFx02oIC74WKsV4oXNzUK8F5etp7QjM65NLnRT8
CH3OP/DFtMzhUP63268QZKhanAjZkqp+TXbeXJDhZviQXGVfL2hZZYlLQEoyc77W
1Bl3W4Wk7cBvUi1QLiPBShZfii1OscifFk5Q0I+LmpgSO0xkfNu6xZsMXZea6PiF
9qGc+kDZF1rTrwsLKzwDN8VeM2P968icZGPUEuEDGtpiVHk2FFBTTIRkTc0qUqaa
6HZuqiVCVhytYtaqHGDHnjPWQOE06I6sjai89Tq3InTRHrf99X2QNqlT2JCiKZxJ
4LjCOpkCgYEA4b7FZaOwP+2OqNVw2DLQrpGe6OGvqXOmMRTU/Dj70Nsf2ghj4vWb
d8EcdXOaChBM5oOteyCa7b5LOpLb20iQz3tp/lDjtCnCRuBUuceNdrk2XI6dxntA
Ux4bg/MIlzqiipJ+dJo0kaDJdwL7CHuQ8iA8jHMgA852XpO5b7p3H/cCgYEAz6EA
eHtmBW0cX33pDLSOJvgYr+silH6N/7StuZ5gQJBI6F/a3z1HFaH+ZJS1nOb3GoFD
UpcDhnP/eFbFd2dOX8/m5yHAyvfrUlr0qDexBjXDqw96HuZE6pS+75aDLt04kTGT
egz6SwKxs0E0bLy+G39cplEkuY3raESx5sNaqJsCgYAPCRLCs0VQ7LScwCKU88V8
awyHfEij46UFDdsltXHoNkAH2Jk2i59AOad4lyuCUhWdINYUJlbLUOpXy2JDV7D1
cMXdf2u7GzDqYZSjDwx4BNv/DCysBJeDMbUpc611zRz4V8t+XqrzrB7fA17O8NP1
nHoL7LsMJdsyb2pha6z1fwKBgQCuLt96M+uOuc6HvdV5Ny/aOWBclOJZuSHfVvA3
PEp7X5AKgf/YMEwmNdR5BNinXIwIzFByRQZMEZxMlF7soNn7Pyry1DotDHd6i5uc
U7xK/We9ZiqJKZy/PzI/RQGgmy4NgI28Yo7HxubU/urAHkdOQjazwHcSw6CtxJOK
iHDR6QKBgQDVOfatHeay6vylPUUEw/ACckjsWMnyG7Itk801SIYQdpenpdUtQXXX
77Myc4h0YqMA5vx1X7dspeK6FP3zIGfBXnYIngN/0K9GAsuIyd6j0WKTqEm9geTQ
zjnahg4QbM6Yed3xgz94nkFpeKvkQz/5vPrKy041E/JMROGYF8/wbQ==
-----END RSA PRIVATE KEY-----
        """


@pytest.fixture
def symphony_storage():
    """
    Yields temporary symphony storage.

    Yields:
        str:
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage
