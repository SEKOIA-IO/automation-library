from collections.abc import Iterator

from jsonpath_ng import parse


class ValueExtractor:
    """
    Base class for value extractors.

    A value extractor is used to extract observable values from a config.
    """

    def extract(self, config: dict) -> Iterator[str]:
        """
        Extract observable values from the given config
        """
        raise NotImplementedError()


class JSONPathValueExtractor(ValueExtractor):
    """
    Value extractor based on a json path
    """

    def __init__(self, path: str):
        self.parsed = parse(path)

    def extract(self, config: dict) -> Iterator[str]:
        for res in self.parsed.find(config):
            yield res.value


class SeparatedValueExtractor(ValueExtractor):
    """
    Value extractor for semicolon separated strings
    """

    def __init__(self, path: str, separator: str):
        self.path = path
        self.separator = separator

    def extract(self, config: dict) -> Iterator[str]:
        yield from config.get(self.path, "").split(self.separator)


class DummyExtractor(ValueExtractor):
    """
    Dummy extractor yielding nothing
    """

    def extract(self, config: dict) -> Iterator[str]:
        """
        Extract observable values from the given config
        """
        yield from ()
