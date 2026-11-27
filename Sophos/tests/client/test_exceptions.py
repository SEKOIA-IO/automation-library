from sophos_module.client.exceptions import SophosApiAuthenticationError, SophosGraphQLError


def test_graphql_error_message():
    error = SophosGraphQLError(
        [{"message": "internal service error", "path": ["detectionPoll"], "extensions": {"code": "DOWNSTREAM"}}]
    )
    assert error.codes == ["DOWNSTREAM"]
    assert error.errors[0]["message"] == "internal service error"
    assert str(error) == "internal service error (code: DOWNSTREAM, path: ['detectionPoll'])"


def test_graphql_error_without_extensions():
    error = SophosGraphQLError([{"message": "first"}, {"message": "second", "extensions": None}])
    assert error.codes == [None, None]
    assert str(error) == "first (code: None, path: None); second (code: None, path: None)"


def test_authentication_error():
    assert str(SophosApiAuthenticationError("Authentication failed")) == "Authentication failed"
