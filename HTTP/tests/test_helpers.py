import pytest

from http_module.helpers import params_as_dict


@pytest.mark.parametrize(
    "input_params, expected_output",
    [
        ("param1=value1&param2=value2", "param1=value1&param2=value2"),
        ({"param1": "value1", "param2": "value2"}, {"param1": "value1", "param2": "value2"}),
        ('{"param1": "value1", "param2": "value2"}', {"param1": "value1", "param2": "value2"}),
        ("not a dict", "not a dict"),
        (None, None),
    ],
)
def test_params_as_dict(input_params, expected_output):
    assert params_as_dict(input_params) == expected_output
