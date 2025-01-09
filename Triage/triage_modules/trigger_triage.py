import json
import re
import time
from datetime import datetime
from typing import Any
from statistics import stdev

from cached_property import cached_property
from dateutil.relativedelta import relativedelta
from sekoia_automation.trigger import Trigger
from triage import Client
from triage.client import ServerError

from triage_modules.utils import IPV4_ADDRESS_REGEX, URL_REGEX

domain_regex = r"\b((?=[a-z0-9-_]{1,63}\.)(xn--)?[a-z0-9]+([-_]+[a-z0-9]+)*\.)+[a-z]{2,63}\b"
domain_port_regex = r"\b((?=[a-z0-9-_]{1,63}\.)(xn--)?[a-z0-9]+([-_]+[a-z0-9]+)*\.)+[a-z]{2,63}\b:[0-9]{2,5}"
hash_regex = "^([a-f0-9]{32}|[0-9a-f]{40}|[0-9a-f]{64}|[0-9a-f]{128})$"
ipv4_port_regex = (
    r"^(?:(?:\d|[01]?\d\d|2[0-4]\d|25[0-5])\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d|\d)(?:\d{1,2})?:[0-9]{2,5}$"
)
url_without_scheme = (
    r"\b(((?=[a-z0-9-_]{1,63}\.)(xn--)?[a-z0-9]+([-_]+[a-z0-9]+)*\.)+[a-z]{2,63}|(?:(?:\d|[01]?\d\d|2[0-4]\d|"
    + r"25[0-5])\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d|\d)(?:\d{1,2})?)\b(:\d{2,5})?\/(?:[-a-zA-Z0-9()@:%_\\+.~#?&\\/=]*)"
)


class TriageTrigger(Trigger):
    """
    Base class for Triage triggers.
    """

    @property
    def api_key(self):
        return self.module.configuration["api_key"]

    @property
    def api_url(self):
        return self.module.configuration["api_url"]

    @property
    def exclude_signed(self):
        return self.configuration.get("exclude_signed", False)

    @property
    def exclude_suspicious_analysis(self):
        return self.configuration.get("exclude_suspicious_analysis", False)

    @property
    def frequency(self):
        return self.configuration["frequency"]

    @cached_property
    def client(self) -> Client:
        return Client(token=self.api_key, root_url=self.api_url)

    def run(self):
        self.log("Trigger starting")
        try:
            while True:
                self._run()
                time.sleep(self.frequency)
        finally:
            self.log("Trigger stopping")

    def _run(self):
        raise NotImplementedError()


class TriageConfigsTrigger(TriageTrigger):
    def _run(self):
        triage_raw_results = list()
        for malware in self.configuration["malware_list"]:
            sample_ids = self.get_malware_samples(malware, self.frequency)
            if sample_ids:
                iocs = self.get_malware_iocs(malware, sample_ids)
                triage_raw_results.append(iocs)
        if triage_raw_results:
            json_triage_raw_results = json.dumps(triage_raw_results)

            work_dir = self.data_path.joinpath("triage_results")
            work_dir.mkdir(parents=True, exist_ok=True)
            file_name = work_dir.joinpath(f"triage{int(datetime.now().timestamp())}.json")
            with file_name.open("w") as f:
                f.write(json_triage_raw_results)

            directory = str(work_dir.relative_to(self.data_path))
            file_path = str(file_name.relative_to(work_dir))
            self.log(f"Create event with {len(triage_raw_results)} results")
            self.send_event(
                event_name=f"Triage raw results {file_name}",
                event=dict(file_path=file_path),
                directory=directory,
                remove_directory=True,
            )

    def get_valid_c2(self, c2s: list[str]) -> list[str]:
        valid_c2s = list()
        for c2 in c2s:
            if (
                any(
                    re.match(regex, c2)
                    for regex in [domain_port_regex, domain_regex, ipv4_port_regex, url_without_scheme]
                )
                or IPV4_ADDRESS_REGEX.fullmatch(c2)
                or URL_REGEX.fullmatch(c2)
            ):
                valid_c2s.append(c2)
        return valid_c2s

    def get_malware_samples(self, malware: str, period: int) -> list[str]:
        until = (datetime.now() - relativedelta(seconds=+period)).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            res = self.client.search(query=f"family:{malware}", max=2000)
            return [sample["id"] for sample in res if sample["submitted"] > until]
        except ServerError as ex:
            self.log(f"Requests to Triage failed: {str(ex)}", level="error")
            return []
        except Exception as ex:
            self.log(f"Failed to search for samples (family:{malware}): {str(ex)}", level="error")
            self.log_exception(ex)
            return []

    def check_sample_signature(self, sample_id: str) -> bool:
        try:
            # Get static report for PE metadata
            static_report = self.client.static_report(sample_id=sample_id)
            signers = static_report.get("files")[0]["metadata"]["pe"]["code_sign"]["signers"]
            for value in signers:
                if isinstance(value["validity"]["trusted"], list):
                    for entry in value["validity"]["trusted"]:
                        if entry:
                            signature = entry
                else:
                    signature = value["validity"]["trusted"]
            return signature
        except (KeyError, TypeError):
            return False

    def check_suspicious_analysis(self, sample_id: str, data: dict) -> bool:
        try:
            tags: list[str] = list()
            tasks: list[dict] = list()
            tags = data.get("analysis", {}).get("tags")
            if len(tags) == 0 or "linux" in tags:
                return False
            tasks = data.get("tasks", [])
            scores = []
            for t in tasks:
                if t.get("kind") == "behavioral" and "score" in t:
                    scores.append(t["score"])
            if len(scores) < 2:
                self.log(f"PE in {sample_id} report does not have at least two dynamic analysis")
                return True
            if stdev(scores) > 2.5:
                self.log(f"PE in {sample_id} has an important score gap between some dynamic analysis")
                return True
            else:
                return False
        except (KeyError, TypeError):
            return False

    def get_sample_iocs(self, malware: str, sample_id: str) -> dict:
        sample_iocs: dict[str, list] = dict()
        sample_iocs["sample_c2s"] = list()
        sample_iocs["sample_urls"] = list()
        sample_iocs["sample_hashes"] = list()

        try:
            data = self.client.overview_report(sample_id=sample_id)
            if self.exclude_signed:
                sig = self.check_sample_signature(sample_id=sample_id)
                # Check if the first submitted binary is signed then return nothing
                if sig:
                    self.log(f"PE in {sample_id} report has a trusted signature")
                    return sample_iocs
            if self.exclude_suspicious_analysis:
                suspicious = self.check_suspicious_analysis(sample_id=sample_id, data=data)
                if suspicious:
                    return sample_iocs
        except ServerError as ex:
            self.log(f"Requests to Triage failed: {str(ex)}", level="error")
            return sample_iocs
        except Exception as ex:
            self.log(f"Failed to get report for sample {sample_id}: {str(ex)}", level="error")
            self.log_exception(ex)
            return sample_iocs
        extracted = data.get("extracted", []) or []  # In case it is None
        for extract in extracted:
            self._handle_extracted(extract, sample_iocs, malware)

        targets = data.get("targets", []) or []  # In case it is None
        for target in targets:
            if "tags" in target and f"family:{malware}" in target["tags"]:
                if "md5" in target:
                    sample_iocs["sample_hashes"].append(target["md5"])
                if "sha1" in target:
                    sample_iocs["sample_hashes"].append(target["sha1"])
                if "sha256" in target:
                    sample_iocs["sample_hashes"].append(target["sha256"])
                if "sha512" in target:
                    sample_iocs["sample_hashes"].append(target["sha512"])

        return sample_iocs

    def _handle_extracted(self, extract: dict, sample_iocs: dict, malware: str):
        config = extract.get("config", {})
        if "c2" in config and "family" in config and config["family"] == malware:
            sample_iocs["sample_c2s"] += self.get_valid_c2(config["c2"])
        if "attr" in config and "family" in config and "url4cnc" in config["attr"] and config["family"] == malware:
            if isinstance(config["attr"]["url4cnc"], str):
                sample_iocs["sample_c2s"] += self.get_valid_c2(list(config["attr"]["url4cnc"]))
            elif isinstance(config["attr"]["url4cnc"], list):
                sample_iocs["sample_c2s"] += self.get_valid_c2(config["attr"]["url4cnc"])
        if "dropper" in extract and extract["dropper"].get("urls"):
            sample_iocs["sample_urls"] += self.get_valid_c2([x["url"] for x in extract["dropper"]["urls"]])

    def _handle_target(self, target: dict, sample_iocs: dict, malware: str):
        if f"family:{malware}" not in target.get("tags", []):
            return
        if "md5" in target:
            sample_iocs["sample_hashes"].append(target["md5"])
        if "sha1" in target:
            sample_iocs["sample_hashes"].append(target["sha1"])
        if "sha256" in target:
            sample_iocs["sample_hashes"].append(target["sha256"])
        if "sha512" in target:
            sample_iocs["sample_hashes"].append(target["sha512"])

    def get_malware_iocs(self, malware: str, sample_ids: list[str]) -> dict:
        malware_iocs: dict[str, Any] = dict()
        malware_iocs["malware"] = malware
        malware_iocs["samples"] = dict()
        for sample_id in sample_ids:
            sample_iocs = self.get_sample_iocs(malware, sample_id)
            malware_iocs["samples"][sample_id] = sample_iocs
        return malware_iocs
