from client.errors import AuthenticationFailed


def test_authentication_failed():
    response_json = {
        "error_uri": "https://iam.cloud.trellix.com/ErrorCodes.html#database-client-unknown",
        "tid": 233264798,
        "error_description": "Client unknown.",
        "error": "invalid_client",
        "message": "Client unknown.",
        "client_id": "11111111111111111111111111&&",
        "status": 401,
    }

    error = AuthenticationFailed.from_http_response(response_json)
    assert error.client_id == response_json["client_id"]
    assert error.code == response_json["error"]
    assert error.description == response_json["error_description"]
    assert error.uri == response_json["error_uri"]
    assert (
        str(error)
        == f"Authentication failed for client '{response_json['client_id']}' code='{response_json['error']}' description='{response_json['error_description']}' uri='{response_json['error_uri']}'"
    )


def test_authentication_failed2():
    response_json = {
        "error_uri": "https://iam.cloud.trellix.com/ErrorCodes.html#database-client-unknown",
        "tid": 233264798,
        "error": "invalid_client",
        "message": "Client unknown.",
        "status": 401,
    }

    error = AuthenticationFailed.from_http_response(response_json)
    assert error.code == response_json["error"]
    assert error.uri == response_json["error_uri"]
    assert str(error) == f"Authentication failed code='{response_json['error']}' uri='{response_json['error_uri']}'"
