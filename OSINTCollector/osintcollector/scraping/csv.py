import csv
from collections.abc import Iterable

from osintcollector.scraping.errors import ScrapingError
from osintcollector.scraping.line import LineScraper


class CSVScraper(LineScraper):
    def _extract_line(self, lines):
        delimiter, lines = self._get_delimiter(lines)
        quotechar = self.config.get("quotechar", '"')
        reader = csv.reader(lines, delimiter=delimiter, quotechar=quotechar, skipinitialspace=True)
        yield from enumerate(reader)

    def _get_delimiter(self, lines: Iterable[str]) -> tuple[str, Iterable[str]]:
        separator = self.config.get("separator", ",")

        if len(separator) == 1:
            return separator, lines

        # csv.reader only accept one line delimiters
        # So we replace the delimiter with a new one.
        candidates = ["|", "#", "$", "~", "€", "£"]
        for candidate in candidates:
            if all(candidate not in line for line in lines):
                old_separator = separator
                separator = candidate
                lines = (line.replace(old_separator, separator) for line in lines)
                return separator, lines

        raise ScrapingError("Impossible to find a valid csv delimiter", self.config)
