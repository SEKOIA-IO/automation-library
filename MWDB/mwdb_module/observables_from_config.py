import uuid
from collections.abc import Iterator
from datetime import datetime
from itertools import zip_longest

from tldextract import tldextract

from mwdb_module.model import MalwareRule
from mwdb_module.utils import datetime_to_str, IPV4_ADDRESS_REGEX, OBSERVABLES_MAPPING


class ObservablesFromConfigForRule:
    def __init__(self, rule: MalwareRule, config: dict):
        self._rule: MalwareRule = rule
        self._config: dict = config
        self._global_ports: set[int] = set()
        self._observables: list[dict] = []

    def extract_observables(self) -> list[dict]:
        """
        Extract the observables from the config
        """
        self._extract_global_ports()
        for match, port in self._match_iterator():
            self._handle_match(match, port)
        return self._observables

    def _extract_global_ports(self):
        if self._rule.global_port_extractor:
            self._global_ports = {int(p) for p in self._rule.global_port_extractor.extract(self._config)}

    def _match_iterator(self) -> Iterator[tuple[str, str | None]]:
        """
        Yield tuples of match with potentially the associated port
        """
        yield from zip_longest(
            self._rule.extractor.extract(self._config),
            self._rule.port_extractor.extract(self._config),
        )

    def _get_decoys(self) -> list:
        if self._rule.decoys_extractor:
            return list(self._rule.decoys_extractor.extract(self._config))
        return []

    def _handle_match(self, match: str, port: str | None):
        if not isinstance(match, str):
            # We didn't extract a string so we can't create an observable
            return
        try:
            value, stix_type, potential_port = self._get_final_value_and_type(match)
            if potential_port:
                port = str(potential_port)
        except ValueError:
            return

        if self._is_decoy(value, stix_type):
            return

        observable = {
            "type": stix_type,
            "id": f"{stix_type}--{str(uuid.uuid4())}",
            "value": value,
            "x_inthreat_tags": [
                {
                    "name": self._config["type"],
                    "valid_from": datetime_to_str(datetime.utcnow()),
                }
            ],
        }
        if port or self._global_ports:
            observable_ports = set(self._global_ports)  # Copy of the global port
            if port:
                observable_ports.add(int(port))
            observable["x_inthreat_history"] = [
                {
                    "name": "MWDB",
                    "date": datetime_to_str(datetime.utcnow()),
                    "value": {"ports": list(observable_ports)},
                }
            ]
        self._observables.append(observable)

    def _get_final_value_and_type(self, value: str) -> tuple[str, str, int | None]:
        """
        Parses the value to get its real type and tries to extract the port from it when possible
        """
        stix_type = self._rule.type
        # Remove port for domains
        port = None
        if stix_type == "domain-name":
            value, *remaining = value.split(":", 1)
            if remaining and remaining[0].isdigit():
                port = int(remaining[0])
        if stix_type == "url" and self._rule.protocol and not value.startswith(self._rule.protocol):
            # Add protocol to url if needed and possible
            value = f"{self._rule.protocol}://{value}"
        if stix_type == "url" and not (value.startswith("http") or value.startswith("ftp")):
            value = f"http://{value}"
        # In case the domain is in fact an IP
        if stix_type == "domain-name" and IPV4_ADDRESS_REGEX.fullmatch(value):
            return value, "ipv4-addr", port
        if stix_type in OBSERVABLES_MAPPING and not OBSERVABLES_MAPPING[stix_type].fullmatch(value):
            raise ValueError()
        if stix_type == "domain-name":
            extracted = tldextract.extract(value)
            if not extracted.suffix:
                raise ValueError()
        return value, stix_type, port

    def _is_decoy(self, value: str, stix_type: str):
        """
        Check whether the given value is a decoy or not.
        """
        for decoy in self._get_decoys():
            if stix_type in ["ipv4'-addr", "domain-name"] and decoy == value:
                # Exact match
                return True
            if stix_type == "url":
                # Check if the url has a domain belonging to the decoys
                extracted = tldextract.extract(value)
                if decoy in [
                    extracted.fqdn,
                    extracted.registered_domain,
                    extracted.ipv4,
                ]:
                    return True
        return False
