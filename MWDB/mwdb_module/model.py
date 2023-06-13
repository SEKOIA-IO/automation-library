from dataclasses import dataclass

from mwdb_module.extractors import DummyExtractor, ValueExtractor


@dataclass
class MalwareRule:
    type: str
    extractor: ValueExtractor
    protocol: str | None = None
    ignore_wrong_values: bool = False

    # port extractor to extract port related with the observable
    # i.e. [{"host": "8.8.8.8", "port": 80}]
    port_extractor: ValueExtractor = DummyExtractor()

    # Extractor to get ports common to all observables
    # i.e. {"port": 80, "ips": ["8.8.8.8"]
    global_port_extractor: ValueExtractor | None = None

    # Extractor to get decoys from the config
    decoys_extractor: ValueExtractor | None = None
