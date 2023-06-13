from osintcollector.scraping.base import Scraper
from osintcollector.scraping.csv import CSVScraper
from osintcollector.scraping.errors import ScrapingRulesError
from osintcollector.scraping.html import HTMLScraper
from osintcollector.scraping.json import JSONScraper
from osintcollector.scraping.line import LineScraper
from osintcollector.scraping.regex import RegexScraper

SCRAPERS = {
    "line": LineScraper,
    "html": HTMLScraper,
    "json": JSONScraper,
    "regex": RegexScraper,
    "csv": CSVScraper,
}


def get_scraper(config: dict) -> Scraper:
    """
    Get a scraper implementation given a specific configuration
    """
    if config["global_format"] in SCRAPERS:
        return SCRAPERS[config["global_format"]](config)

    raise ScrapingRulesError(
        config,
        f"Could not find scraping implementation for '{config['global_format']}' format",
    )
