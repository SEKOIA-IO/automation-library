import pytest

from bitdefender.helpers import handle_uri, parse_push_block


def test_handle_uri_normalizes_http_and_missing_scheme():
    assert handle_uri("http://gravityzone.example/") == "https://gravityzone.example"
    assert handle_uri("gravityzone.example/") == "https://gravityzone.example"


def test_parse_push_block_validation_errors():
    with pytest.raises(ValueError, match="'type' and 'rules' are required"):
        parse_push_block({"type": "hash", "rules": []})

    with pytest.raises(ValueError, match="'details' is required"):
        parse_push_block({"type": "hash", "rules": [{}]})

    with pytest.raises(ValueError, match="Unsupported type"):
        parse_push_block({"type": "unsupported", "rules": [{"details": {}}]})
