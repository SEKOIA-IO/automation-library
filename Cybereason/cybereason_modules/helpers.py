from collections.abc import Generator
from typing import Any

import orjson
import requests
from bs4 import BeautifulSoup

from cybereason_modules.exceptions import InvalidResponse


def extract_models_from_malop(
    malop: dict[str, Any], items: list | None, model_class: str
) -> Generator[dict[str, Any], None, None]:
    """
    Extract and yield models from a malop

    :param dict malop: The malop
    :param str origin: The name of the field holding the models in the malop
    :param str model_class: The class of the model
    """
    # Get malop identifier and set metadata
    malop_uuid = malop["guid"]
    metadata = {"metadata": {"malopGuid": malop_uuid, "timestamp": malop["lastUpdateTime"]}}

    # for each model
    items = items or []
    for item in items:
        # add metadata
        model = dict(item)
        model.update(metadata)

        # add class if not existing
        if "@class" not in model:
            model["@class"] = model_class

        yield model


def merge_suspicions(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Merge two suspicions
    """
    if left is None or len(left) == 0:
        return right

    if right is None or len(right) == 0:
        return left

    return {
        "firstTimestamp": min(left["firstTimestamp"], right["firstTimestamp"]),
        "evidences": sorted(list(set(left["potentialEvidence"]) | set(right["potentialEvidence"]))),
    }


def validate_response_not_login_failure(response: requests.Response) -> bool:
    """
    Validate the API response is not a login failure

    Cybereason has an authentication system for API called ACB (Act always as if the Client is a Browser).
    This authentication systems respects the following properties:
    - Always return status code 200, even when the login has failed
    - Return HTML code if the login has failed
    - Use session and set the session_id in the cookies

    :param bytes content: The content of the response
    :return: False if the content is the login page, True otherwise
    :rtype: bool
    """
    content = response.content

    # if the content a json response
    try:
        orjson.loads(content)
        return True
    except Exception:
        pass

    try:
        # Parse the html content
        soup = BeautifulSoup(content.decode("utf-8"), "html.parser")

        app_login_tags = soup.find_all("app-login")
        # if the app-login tag is found
        if len(app_login_tags) > 0:
            # it's the login page
            return False

        return True
    except Exception as error:
        raise InvalidResponse(response) from error
