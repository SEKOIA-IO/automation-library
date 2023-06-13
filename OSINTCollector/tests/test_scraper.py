import pytest
from osintcollector.scraping import get_scraper
from osintcollector.scraping.errors import ScrapingRulesError


@pytest.fixture
def invalid_jsonpath_item_format():
    return {
        "name": "Invalid JSONPath",
        "identity": "Invalid JSONPath",
        "url": "url",
        "frequency": 172800,
        "global_format": "json",
        "fields": ["ipv4-addr"],
        "item_format": ["$.IP Range"],
        "cache_results": False,
    }


def test_invalid_jsonpath(invalid_jsonpath_item_format):
    with pytest.raises(ScrapingRulesError):
        scraper = get_scraper(invalid_jsonpath_item_format)
        scraper.check_configuration()


@pytest.fixture
def invalid_jsonpath_iterate_over():
    return {
        "name": "Invalid JSONPath",
        "identity": "Invalid JSONPath",
        "url": "url",
        "frequency": 172800,
        "global_format": "json",
        "fields": ["ipv4-addr"],
        "item_format": ["$.ip"],
        "iterate_over": "$.IP Range",
        "cache_results": False,
    }


def test_invalid_jsonpath_iterate(invalid_jsonpath_iterate_over):
    with pytest.raises(ScrapingRulesError):
        scraper = get_scraper(invalid_jsonpath_iterate_over)
        scraper.check_configuration()
