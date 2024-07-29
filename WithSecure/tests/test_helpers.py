import json

import requests

from withsecure.helpers import human_readable_api_error


def test_human_readable_api_error_with_error():
    response = requests.Response()
    response.status_code = 400
    response._content = json.dumps(
        {
            "message": "Bad request because of invalid parameters or data.",
            "code": 400000,
            "transactionId": "0000-someTransactionId",
        }
    ).encode()

    assert (
        human_readable_api_error(response)
        == "WithSecure API returned 'Bad request because of invalid parameters or data.' (status=400)"
    )


def test_human_readable_api_error_with_error_and_details():
    response = requests.Response()
    response.status_code = 400
    response._content = json.dumps(
        {
            "message": "Request parameter(s) have wrong format. Check details.",
            "code": 400001,
            "transactionId": "0000-someTransactionId",
            "details": {"invalidParam": "someTimestamp", "invalidValue": "2022-10-6T12:1:14Z"},
        }
    ).encode()

    assert human_readable_api_error(response) == (
        "WithSecure API returned 'Request parameter(s) have wrong format. Check details.' "
        '- {"invalidParam": "someTimestamp", "invalidValue": "2022-10-6T12:1:14Z"} '
        "(status=400)"
    )


def test_human_readable_api_support_exception():
    response = requests.Response()
    response.status_code = 400
    response._content = b"invalid json"
    assert human_readable_api_error(response) == "WithSecure API rejected our request (status=400)"

    def raise_exception():
        raise Exception()

    response.json = raise_exception
    assert human_readable_api_error(response) == "WithSecure API rejected our request (Exception)"


def test_human_readable_api_error_with_transaction_id():
    response = requests.Response()
    response.status_code = 503
    response.headers = {"X-Transaction": "0000-1111111111111111"}

    assert (
        human_readable_api_error(response)
        == "WithSecure API rejected our request (status=503 transaction-id=0000-1111111111111111)"
    )
