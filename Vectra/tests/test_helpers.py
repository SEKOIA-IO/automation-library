import pytest

from vectra_modules.helpers import format_boolean


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        (True, "true"),
        (False, "false"),
    ],
)
def test_format_boolean(input_value, expected_output):
    """
    Test the format_boolean function with various inputs.

    Parameters:
    input_value: The value to be tested.
    expected_output: The expected output of the function.
    """
    assert format_boolean(input_value) == expected_output
