from osintcollector.scraping.errors import ScrapingRulesError


class Scraper:
    """
    Base Scraper class

    Scrapers parse raw data and return valuable information from them
    """

    def __init__(self, source: dict):
        self.config = source

    def check_configuration(self):
        """
        Check the configuration to make sure that it is valid

        Raises:
            ScrapingRulesError: when configuration is invalid
        """
        if not self.config.get("fields"):
            raise ScrapingRulesError(self.config, "'fields' is required")

    def run(self, data: str) -> list[dict]:
        """
        Extract valuable information from data following the scraping rules.

        To Implement in subclasses.

        Args:
            data (str): data to parse

        Returns:
            list: A list of dict containing extracted information

        Raises:
            ScrapingError: when data could not properly be parsed
        """
        raise NotImplementedError

    def _get_patterns_to_ignore(self) -> list[str]:
        ignore = self.config.get("ignore")
        if not ignore:
            return []

        patterns: list[str] = []
        for pattern in ignore.split(" "):
            if pattern == "blank":
                patterns += [" ", "\t"]
            elif pattern == "br":
                patterns += [" ", "\t", "\r"]
            else:
                patterns.append(pattern)

        return patterns

    def _get_lines(self, data: str) -> list[str]:
        """
        Extract individual lines from a block of text. Also applies `ignore` rules.

        Args:
            data (str): block of text to parse

        Returns:
            list: valid lines to process
        """
        ignore_patterns: list[str] = self._get_patterns_to_ignore()
        valid_lines: list[str] = []

        for line in data.splitlines():
            # Skip empty lines
            if not line:
                continue

            # Apply ignore rules
            for pattern in ignore_patterns:
                if line.startswith(pattern):
                    break
            else:
                valid_lines.append(line)

        return valid_lines
