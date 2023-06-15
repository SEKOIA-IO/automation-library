class ScrapingRulesError(Exception):
    """
    Exception raised when a scraping rules is incorrect
    """

    def __init__(self, configuration, message):
        self.configuration = configuration
        self.message = message


class ScrapingError(Exception):
    """
    Exception raised when scraper failed to parse a data according to defined scraping rules
    """

    def __init__(self, error, configuration, line=None, value=None):
        self.error = error
        self.configuration = configuration
        self.line = line
        self.value = value
