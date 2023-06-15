import json
import sys
from typing import Any

from jsonpath_ng import JSONPath
from jsonpath_ng.ext import parse
from osintcollector.scraping.base import Scraper
from osintcollector.scraping.errors import ScrapingError, ScrapingRulesError


class JSONScraper(Scraper):
    def check_configuration(self):
        super().check_configuration()

        # item_format should also be present
        if not self.config.get("item_format"):
            raise ScrapingRulesError(self.config, "'item_format' is required")

        # item_format should only contain valid JSONPath Expressions
        for expr in self.config["item_format"]:
            try:
                parse(expr)
            except Exception as e:
                raise ScrapingRulesError(
                    self.config,
                    f"'item_format' contains invalid expression '{expr}': {str(e)}",
                )

        # Iterate Over should also contain a valid JSONPath Expression
        try:
            parse(self.config.get("iterate_over", "$"))
        except Exception as e:
            raise ScrapingRulesError(
                self.config,
                f"'iterate_over' is an invalid expression '{expr}': {str(e)}",
            )

    def run(self, data: str) -> list[dict]:
        """
        Extract data from a JSON Source
        """
        try:
            json_data = json.loads(data)

        except json.decoder.JSONDecodeError:
            raise ScrapingError(configuration=self.config, error=sys.exc_info(), value=data)

        fields: list[str] = self.config["fields"]
        item_format: list[str] = [parse(item) for item in self.config["item_format"]]
        results: list[dict] = []
        json_data = self._get_json_path(json_data, parse(self.config.get("iterate_over", "$")))

        if not isinstance(json_data, list):
            raise ScrapingError(configuration=self.config, error="Data should be iterable", value=data)

        for item in json_data:
            try:
                new_entry = dict()

                for i, field in enumerate(fields):
                    new_entry[field] = self._get_json_path(item, item_format[i])

                results.append(new_entry)
            except ScrapingError:
                pass

        return results

    def _get_json_path(self, obj: Any, path: JSONPath) -> Any:
        """
        Evaluate compiled JSONPath expression against `obj`

        Args:
            obj (any): base object
            path (JSONPath): JSONPath expression to evaluate

        Returns:
            any (): computed JSONPath value
        """
        results = list(map(lambda match: match.value, path.find(obj)))

        if len(results) != 1:
            raise ScrapingError(
                configuration=self.config,
                error=f"Could not get a single result for '{path}'",
                value=obj,
            )

        return results[0]
