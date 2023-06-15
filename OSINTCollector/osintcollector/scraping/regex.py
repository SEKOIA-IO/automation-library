import re

from osintcollector.scraping.base import Scraper
from osintcollector.scraping.errors import ScrapingRulesError


class RegexScraper(Scraper):
    def check_configuration(self):
        super().check_configuration()

        # Make sure item_format is a valid regex
        try:
            re.compile(self.config["item_format"][0])
        except re.error:
            raise ScrapingRulesError(self.config, "Could not compile regex in 'item_format'")

    def run(self, data: str) -> list[dict]:
        """
        Extract data from complex sources using regexes
        """
        lines: list[str] = self._get_lines(data)
        results: list[dict] = []
        regex = re.compile(self.config["item_format"][0])
        fields: list[str] = self.config["fields"]

        for _, line in enumerate(lines):
            for match in regex.finditer(line):
                new_entry = dict()

                for i, value in enumerate(match.groups()):
                    if value is not None:
                        new_entry[fields[i]] = value

                if new_entry:
                    results.append(new_entry)

        return results
