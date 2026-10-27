from googlethreatintelligence.client import VTAPIConnector


def test_api_key_stored_on_connector():
    """Verify that api_key is correctly stored on the connector instance."""
    connector = VTAPIConnector(api_key="MY_REAL_KEY")
    assert connector.api_key == "MY_REAL_KEY"
    assert connector.headers == {"x-apikey": "MY_REAL_KEY"}


def test_api_key_used_in_headers():
    """Verify that the x-apikey header matches the provided key."""
    connector = VTAPIConnector(api_key="ANOTHER_KEY")
    assert connector.headers["x-apikey"] == "ANOTHER_KEY"
