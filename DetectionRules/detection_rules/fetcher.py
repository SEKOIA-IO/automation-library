import hashlib
import io
import logging

import idstools.rule
from idstools.rule import Rule

from detection_rules.archive import RuleArchive
from detection_rules.cache import Cache
from detection_rules.serializer import RuleSerializer


class RulesFetcher:
    def __init__(self, archives: list, cache: Cache):
        self._logger = logging.getLogger(__name__)
        self._archives = archives
        self._cache = cache

    def fetch_rules(self):
        rules = []
        for archive in self._archives:
            archive_rules = self.fetch_from_url(
                archive["url"],
                archive["type"],
                archive.get("version"),
                archive.get("oinkcode"),
            )
            rules += archive_rules
        return rules

    def fetch_from_url(self, url: str, rule_type: str, rule_version: str | None = None, oinkcode: str | None = None):
        """
        Fetch rules from the given url
        """
        self._logger.info(f"Fetching rules for {url}")
        last_md5 = self._cache.get(url)
        with RuleArchive(url, oinkcode) as archive:
            if last_md5 == archive.remote_md5:
                self._logger.info("Remote file is unchanged, ignoring.")
                return []
            archive.download()
            files = archive.extract_files()
            result = self._process_files(url, files, rule_type, rule_version)
            self._cache.set(url, archive.remote_md5)
        return result

    def _process_files(self, url: str, files: dict, rule_type: str, rule_version: str | None = None):
        """
        Process the file from the rule archive.

        It will read the files and parse the rules inside them.
        """
        rules = []
        serializer = RuleSerializer(rule_type, rule_version)
        for filename, rule_file in files.items():
            if not filename.endswith(".rules") or filename.endswith("deleted.rules"):
                continue
            file_md5 = self.compute_md5(rule_file)
            cache_key = f"{url}|{filename}"
            last_file_md5 = self._cache.get(cache_key)
            if file_md5 == last_file_md5:
                self._logger.debug(f"File {filename} is unchanged...")
                continue

            self._logger.debug(f"Processing file {filename}...")
            parsed_rules = self.parse_rule_file(rule_file)
            rules += serializer.to_stix(parsed_rules)
            self._logger.debug("Processed.")
            self._cache.set(cache_key, file_md5)
        return rules

    @staticmethod
    def parse_rule_file(rule_file) -> list[Rule]:
        return idstools.rule.parse_fileobj(io.BytesIO(rule_file))

    @staticmethod
    def compute_md5(rule_file) -> str:
        return hashlib.md5(rule_file).hexdigest()
