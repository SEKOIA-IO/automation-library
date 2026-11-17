from netskope_modules.constants import MESSAGE_CANNOT_CONSUME_SERVICE


def test_message_cannot_consume_service_matches_netskope_wording():
    # Compared verbatim with the `message` field of Netskope 403 responses to stop the consumer
    assert MESSAGE_CANNOT_CONSUME_SERVICE == "You cannot consume this service"
