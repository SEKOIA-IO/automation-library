from asset_connector.harfanglab_connector.helper import handle_uri


def test_handle_uri():
    assert handle_uri("http://example.com") == "https://example.com"
    assert handle_uri("https://example.com/") == "https://example.com"
    assert handle_uri("example.com") == "https://example.com"
    assert handle_uri("https://example.com/path/to/resource") == "https://example.com/path/to/resource"
    assert handle_uri("http://example.com/path/to/resource") == "https://example.com/path/to/resource"
    assert handle_uri("example.com/path/to/resource") == "https://example.com/path/to/resource"
