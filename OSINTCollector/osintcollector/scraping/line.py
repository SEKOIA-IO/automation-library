from collections.abc import Iterator

from osintcollector.scraping.base import Scraper
from osintcollector.scraping.errors import ScrapingError


class LineScraper(Scraper):
    def run(self, data: str) -> list[dict]:
        lines: list[str] = self._get_lines(data)
        fields: list[str] = self.config["fields"]
        results: list[dict] = []

        for line_number, line in self._extract_line(lines):
            line_results: dict = {}

            # Fail if the line is incorrectly formatted
            if len(line) != len(fields):
                raise ScrapingError(
                    "Line does not have specified format",
                    self.config,
                    line_number,
                    line,
                )

            for index, field in enumerate(fields):
                # Ignore _ fields
                if field != "_":
                    line_results[field] = line[index]

            results.append(line_results)

        return results

    def _extract_line(self, lines: list[str]) -> Iterator[tuple[int, list[str]]]:
        """
        Generator to iterate over lines with the separator applied.

        Args:
            lines (list): list of lines to process

        Returns:
            tuple: First item is the line number, second item is a list of strings
                extracted by applying the separator.
        """
        for line_number, line in enumerate(lines):
            # When no separator is specified, do not split the line
            line_parts: list[str] = [line]

            if self.config.get("separator"):
                line = line.replace('"', "")

                # Determine exact separator
                separator = self.config["separator"]
                if separator == "blank":
                    separator = " "
                elif separator == "tab":
                    separator = "\t"

                line_parts = line.split(separator)

            yield (line_number, line_parts)
