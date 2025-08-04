import re
import uuid
from datetime import datetime

from sekoia_automation.action import Action

from triage_modules.utils import datetime_to_str, IPV4_ADDRESS_REGEX, URL_REGEX

domain_regex = r"\b((?=[a-z0-9-_]{1,63}\.)(xn--)?[a-z0-9]+([-_]+[a-z0-9]+)*\.)+[a-z]{2,63}\b$"
domain_port_regex = r"\b((?=[a-z0-9-_]{1,63}\.)(xn--)?[a-z0-9]+([-_]+[a-z0-9]+)*\.)+[a-z]{2,63}\b:\d{2,5}$"
hash_regex = "^([a-f0-9]{32}|[0-9a-f]{40}|[0-9a-f]{64}|[0-9a-f]{128})$"
ipv4_port_regex = r"^(?:(?:\d|[01]?\d\d|2[0-4]\d|25[0-5])\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d|\d)(?:\d{1,2})?:\d{2,5}$"
url_without_scheme = (
    r"\b(((?=[a-z0-9-_]{1,63}\.)(xn--)?[a-z0-9]+([-_]+[a-z0-9]+)*\.)+[a-z]{2,63}|(?:(?:\d|[01]?\d\d|2[0-4]\d|"
    + r"25[0-5])\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d|\d)(?:\d{1,2})?)\b(:\d{2,5})?\/(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)"
)


class TriageToObservablesAction(Action):
    def run(self, arguments: dict) -> dict:
        triage_raw_results = self.json_argument("triage_raw_results", arguments)
        objects = dict()
        for malware_results in triage_raw_results:
            objects.update(self.iocs_triage(malware_results))
        bundle = {
            "type": "bundle",
            "id": f"bundle--{str(uuid.uuid4())}",
            "objects": list(objects.values()),
        }

        return self.json_result("observables", bundle)

    def iocs_triage(self, malware_iocs: dict) -> dict:
        data_unique: dict[str, set] = {"c2": set(), "url": set(), "hash": set()}
        observables: dict[str, dict] = {}
        malware = malware_iocs["malware"]

        for sample_id in malware_iocs["samples"]:
            for c2 in malware_iocs["samples"][sample_id]["sample_c2s"]:
                self._handle_c2(c2, observables, malware, sample_id, data_unique)

            for url in malware_iocs["samples"][sample_id]["sample_urls"]:
                self._handle_url(url, observables, malware, sample_id, data_unique)

            file_hashes = list()
            for _hash in malware_iocs["samples"][sample_id]["sample_hashes"][:4]:
                if re.match(hash_regex, _hash) and _hash not in data_unique["hash"]:
                    data_unique["hash"].add(_hash)
                    file_hashes.append(_hash)
            if file_hashes:
                hash_observable = self.get_file_observables(file_hashes, malware, sample_id)
                mapping_key = self._get_observable_mapping_key(hash_observable)
                observables[mapping_key] = hash_observable

        return observables

    def _handle_url(self, url: str, observables: dict, malware: str, sample_id: str, data_unique: dict):
        if URL_REGEX.fullmatch(url) and url not in data_unique["url"]:
            data_unique["url"].add(url)
            url_observable = self.get_network_observable(url, "url", malware, sample_id)
            if url_observable:
                mapping_key = self._get_observable_mapping_key(url_observable)
                observables[mapping_key] = url_observable

    def _handle_c2(self, c2: str, observables: dict, malware: str, sample_id: str, data_unique: dict):
        observable = dict()

        # when the C2 corresponds to a domain:port
        if re.match(domain_port_regex, c2):
            [c2, port] = c2.split(":")
            if c2 not in data_unique["c2"]:
                data_unique["c2"].add(c2)
                observable = self.get_network_observable(c2, "domain-name", malware, sample_id, port)

        # when the C2 corresponds to a domain name
        elif re.match(domain_regex, c2) and c2 not in data_unique["c2"]:
            data_unique["c2"].add(c2)
            observable = self.get_network_observable(c2, "domain-name", malware, sample_id)

        # when the C2 corresponds to an ipv4:port
        elif re.match(ipv4_port_regex, c2):
            if c2 not in data_unique["c2"]:
                [c2, port] = c2.split(":")
                data_unique["c2"].add(c2)
                observable = self.get_network_observable(c2, "ipv4-addr", malware, sample_id, port)

        # when the C2 corresponds to an ipv4 address
        elif IPV4_ADDRESS_REGEX.fullmatch(c2) and c2 not in data_unique["c2"]:
            data_unique["c2"].add(c2)
            observable = self.get_network_observable(c2, "ipv4-addr", malware, sample_id)

        # when the C2 corresponds to an URL
        elif URL_REGEX.fullmatch(c2) and c2 not in data_unique["c2"]:
            data_unique["c2"].add(c2)
            observable = self.get_network_observable(c2, "url", malware, sample_id)

        elif re.match(url_without_scheme, c2):
            observable = self._handle_no_scheme_url_c2(c2, malware, sample_id, data_unique)

        if observable:
            mapping_key = self._get_observable_mapping_key(observable)
            observables[mapping_key] = observable

    def get_network_observable(
        self,
        value: str,
        stix_type: str,
        malware: str,
        sample_id: str,
        port: str | None = None,
    ) -> dict:
        external_references = [
            {
                "description": f"{malware} sample analyzed by Hatching's sandbox",
                "source_name": "Hatching Triage",
                "url": "https://tria.ge/" + sample_id,
            }
        ]
        if port:
            tags = [
                {
                    "name": malware,
                    "port": port,
                    "valid_from": datetime_to_str(datetime.utcnow()),
                }
            ]
        else:
            tags = [{"name": malware, "valid_from": datetime_to_str(datetime.utcnow())}]
        observable = {
            "type": stix_type,
            "id": f"{stix_type}--{str(uuid.uuid4())}",
            "value": value,
            "x_inthreat_tags": tags,
            "x_external_references": external_references,
        }
        return observable

    def get_file_observables(self, file_hashes: list, malware: str, sample_id: str) -> dict:
        regex_md5 = "^[A-Fa-f0-9]{32}$"
        regex_sha1 = "^[A-Fa-f0-9]{40}$"
        regex_sha256 = "^[A-Fa-f0-9]{64}$"
        regex_sha512 = "^[A-Fa-f0-9]{128}$"

        hashes = dict()
        for _hash in file_hashes:
            if re.match(regex_md5, _hash):
                hashes["MD5"] = _hash
            elif re.match(regex_sha1, _hash):
                hashes["SHA-1"] = _hash
            elif re.match(regex_sha256, _hash):
                hashes["SHA-256"] = _hash
            elif re.match(regex_sha512, _hash):
                hashes["SHA-512"] = _hash

        external_references = [
            {
                "description": f"{malware} sample analyzed by Hatching's sandbox",
                "source_name": "Hatching Triage",
                "url": "https://tria.ge/" + sample_id,
            }
        ]
        observable = {
            "type": "file",
            "id": f"file--{str(uuid.uuid4())}",
            "hashes": hashes,
            "x_inthreat_tags": [{"name": malware, "valid_from": datetime_to_str(datetime.utcnow())}],
            "x_external_references": external_references,
        }
        return observable

    def _get_observable_mapping_key(self, observable: dict) -> str:
        if hashes := observable.get("hashes"):
            for field in ["SHA-256", "SHA-512", "SHA-1", "MD5"]:
                if field in hashes:
                    return f"{observable['type']}:{hashes[field]}"
        port = ""
        if observable.get("x_inthreat_tags", []) and "port" in observable["x_inthreat_tags"][0]:
            port = str(observable["x_inthreat_tags"][0]["port"])
        return f"{observable['type']}:{observable['value']}:{port}"

    def _handle_no_scheme_url_c2(self, c2: str, malware: str, sample_id: str, data_unique: dict) -> dict:
        full_url = "http://" + c2
        if URL_REGEX.fullmatch(full_url) and full_url not in data_unique["c2"]:
            data_unique["c2"].add(full_url)
            return self.get_network_observable(full_url, "url", malware, sample_id)
        return {}
