import json
import re

DICT_REGEX = re.compile(r"^\s*\{(?:[^{}])*\}\s*$")


def params_as_dict(params: str | dict | None) -> dict | str | None:
    """
    Convert a string representation of a dictionary to an actual dictionary.
    If the input is already a dictionary or not a valid dictionary string, it is returned as is.
    """
    if isinstance(params, str) and DICT_REGEX.match(params):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            pass

    return params
