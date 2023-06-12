import string

from sentinelone_module.helpers import generate_password


def assert_password(password: str):
    assert len(password) >= 10, "The length of the password is lesser than 10"
    assert sum(c.islower() for c in password) > 0, "No lowercase character found"
    assert sum(c.isupper() for c in password) > 0, "No uppercase character found"
    assert sum(c.isdigit() for c in password) > 0, "No digit character found"
    assert sum(1 if c in string.punctuation else 0 for c in password) > 0, "No special character found"


def test_generate_password():
    assert_password(generate_password())
    assert_password(generate_password(6))
