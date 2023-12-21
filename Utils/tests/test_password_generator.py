import pytest
import string
from utils.password_generator import PasswordGenerator


@pytest.fixture
def arguments():
    return {"password_length": 20, "number_of_digits": 5, "number_of_special_characters": 2}


@pytest.fixture
def arguments_failure():
    return {"password_length": 10, "number_of_digits": 12, "number_of_special_characters": 8}


def test_password_generator(arguments):
    action = PasswordGenerator()

    results = action.run(arguments)

    digits = string.digits
    special_chars = string.punctuation

    assert results is not None
    assert len(results.get("password")) == 20
    assert sum(char in special_chars for char in results.get("password")) >= 2
    assert sum(char in digits for char in results.get("password")) >= 5


def test_password_generator_failure(arguments_failure):
    action = PasswordGenerator()

    action.run(arguments_failure)
    assert action._error == "number_of_digits + number_of_special_characters must be lower than password_length"
