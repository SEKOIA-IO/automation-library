import pytest
import string
from sekoiaio.operation_center.password_generator import PasswordGenerator

@pytest.fixture
def arguments():
    return {
        password_length = 20
        number_of_digits = 5
        number_of_special_characters = 2
    }

def test_password_generator():
    action = PasswordGenerator(arguments())

    results: dict = action.run(arguments)
    
    digits = string.digits
    special_chars = string.punctuation
    
    assert len(results["password"]) == 20
    assert sum(char in special_chars for char in results["password"]) == 2
    assert sum(char in digits for char in results["password"]) == 5