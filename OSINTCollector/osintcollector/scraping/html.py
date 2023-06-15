import sys
from functools import cached_property

from bs4 import BeautifulSoup
from osintcollector.scraping.base import Scraper
from osintcollector.scraping.errors import ScrapingError


class HTMLScraper(Scraper):
    @cached_property
    def ignore_patterns(self) -> list[str]:
        return self._get_patterns_to_ignore()

    @property
    def fields(self):
        return self.config["fields"]

    def run(self, data: str) -> list[dict]:
        """
        Extract Data from an HTML source (from tables).
        """
        results: list[dict] = []

        for line_number, row in enumerate(self._get_rows(data)):
            result = self._extract_row(line_number, row)
            results.append(result)
        return results

    def _get_rows(self, data: str) -> list:
        """
        Get HTLM Table Rows to parse.

        Will apply `iterate_over` if any was specified.
        """
        soup = BeautifulSoup(data, "html.parser")

        if self.config.get("iterate_over"):
            # iterate_over is an ID
            if self.config["iterate_over"][0] == "#":
                iter_over = soup.find_all("table", id=self.config["iterate_over"][1:])
            # iterate_over is a class
            else:
                iter_over = soup.find_all("table", class_=self.config["iterate_over"][1:])

            soup = BeautifulSoup(str(iter_over), "html.parser")

        return soup.find_all("tr")

    def _extract_row(self, line_number, row) -> dict:
        try:
            line_results: dict = {}

            index = 0
            for cell in row("td"):
                # Skip empty cells
                if not cell or not cell.text:
                    continue

                # Skip cells to ignore
                for pattern in self.ignore_patterns:
                    if cell.text.startswith(pattern):
                        continue

                field = self.fields[index]
                index += 1
                # Ignore '_' fields
                if field == "_":
                    continue

                line_results[field] = cell.text.replace("\n", "")

            return line_results
        except Exception:
            raise ScrapingError(
                configuration=self.config,
                error=sys.exc_info(),
                line=line_number,
                value=str(row),
            )
