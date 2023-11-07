import requests

import helpers


def test_signature_generation():
    sig = helpers.generate_darktrace_signature("public", "private", "/query?param=True", "20230628T125331")
    expected_sig = "77bb1423ac8b591f5cb5fded6d4c6002db824a07"

    assert sig == expected_sig


def test_extract_query():
    params = {"param1": True, "param2": 123}
    url = "https://my_url/endpoint"
    request = requests.Request("GET", url, params=params).prepare()

    query = helpers.extract_query(request)
    expected_query = "/endpoint?param1=True&param2=123"

    assert query == expected_query
