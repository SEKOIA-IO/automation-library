from asset_connector.harfanglab_connector.helper import handle_uri, map_os_type


def test_handle_uri():
    assert handle_uri("http://example.com") == "https://example.com"
    assert handle_uri("https://example.com/") == "https://example.com"
    assert handle_uri("example.com") == "https://example.com"
    assert handle_uri("https://example.com/path/to/resource") == "https://example.com/path/to/resource"
    assert handle_uri("http://example.com/path/to/resource") == "https://example.com/path/to/resource"
    assert handle_uri("example.com/path/to/resource") == "https://example.com/path/to/resource"


def test_map_os_type():
    assert map_os_type("Windows") == 100
    assert map_os_type("Linux") == 200
    assert map_os_type("Android") == 201
    assert map_os_type("macOS") == 300
    assert map_os_type("iOS") == 301
    assert map_os_type("iPadOS") == 302
    assert map_os_type("Solaris") == 400
    assert map_os_type("AIX") == 401
    assert map_os_type("HP-UX") == 402
    assert map_os_type(None) is None
    assert map_os_type("Unknown OS") == 99
