import ipaddress
import json
import time
import gzip
import logging
import uuid
from datetime import datetime, timedelta
from functools import cached_property
from io import BytesIO
from ipaddress import IPv6Network, IPv4Network
from typing import Iterator
from iso3166 import countries

import requests
from sekoia_automation.storage import write
from sekoia_automation.trigger import Trigger


class TriggerFetchIPInfoDatabase(Trigger):
    MAX_HOUR_TAG_VALID_FOR: int = 3 * 24  # Tags are valid for 3 days

    @cached_property
    def api_token(self):
        return self.module.configuration["api_token"]

    @cached_property
    def tags_valid_for(self) -> int:
        if valid_for := self.configuration.get("tags_valid_for"):
            return valid_for
        return min(
            self.MAX_HOUR_TAG_VALID_FOR, self.configuration.get("interval", 24) * 3
        )

    @property
    def database_url(self):
        return f"https://ipinfo.io/data/free/country_asn.json.gz?token={self.api_token}"

    @property
    def interval(self):
        return self.configuration.get("interval", 24) * 3600

    @property
    def identity(self):
        return {
            "id": "identity--1e9f6197-b3a0-4665-88e7-767929d013a4",
            "type": "identity",
            "name": "ipinfo.io",
            "description": "ipinfo.io is a service that maps IP adresses to their Autonomous System Number",
        }

    @staticmethod
    def datetime_to_str(date: datetime) -> str:
        return date.strftime("%Y-%m-%dT%H:%M:%SZ")

    def run(self):
        """
        Entrypoint of the trigger
        """
        self.log("Starting IPInfo.IO trigger")
        try:
            while self.running:
                self._fetch_database()
                logging.debug(f"Sleeping for {self.interval} seconds")
                time.sleep(self.interval)
        finally:
            self.log("IPInfo.IO trigger is stopping")

    def _fetch_database(self):
        """
        This method downloads the 'Free IP to Country + IP to ASN' database
        and create events in chunks to forward its content
        """
        chunks = 0
        for location_chunk_info in self.build_chunks(
            generator=self.get_ipinfo_database(),
            chunk_size=self.configuration.get("chunk_size", 10000),
        ):
            self.create_event_for_chunk(location_chunk_info)
            chunks += 1
        self.log(f"Sent {chunks} chunk events to the API")

    def get_ipinfo_database(self) -> Iterator[list]:
        """
        Downloads the ipinfo.io database in json format
        """
        response = requests.get(self.database_url, stream=True)
        if not response.ok:
            logging.error(f"Server answered with {response.status_code}")
            return

        # Establish validity timeframe for produced observables
        # The tags are valid for 10 days
        now: datetime = datetime.utcnow()
        tag_valid_from: str = self.datetime_to_str(now)
        tag_valid_until: str = self.datetime_to_str(
            now + timedelta(hours=self.tags_valid_for)
        )
        asn_cache: dict[int, dict] = dict()

        with gzip.open(BytesIO(response.content), mode="r") as gz:
            for row in gz.readlines():
                yield from self._parse_db_row(
                    row, tag_valid_from, tag_valid_until, asn_cache
                )

    @staticmethod
    def build_chunks(
        generator: Iterator[list], chunk_size: int
    ) -> Iterator[tuple[list[dict], int]]:
        location_chunk: dict[str, dict] = {}
        chunk_offset: int = 0

        for location_info in generator:
            location_chunk.update({item["id"]: item for item in location_info})

            if len(location_chunk) >= chunk_size:
                yield list(location_chunk.values()), chunk_offset
                location_chunk = {}
                chunk_offset += chunk_size

        if location_chunk:
            yield list(location_chunk.values()), chunk_offset

    def _get_observable_for_asn(
        self, asn_cache: dict, asn_number: int, asn_name: str
    ) -> dict:
        asn_cache[asn_number] = {
            "type": "autonomous-system",
            "id": f"autonomous-system--{str(uuid.uuid4())}",
            "number": asn_number,
            "name": asn_name,
            "x_inthreat_sources_refs": [self.identity["id"]],
        }
        return asn_cache[asn_number]

    def _get_tags(
        self, country_code: str, tag_valid_from: str, tag_valid_until: str, row: bytes
    ) -> list:
        try:
            # check the country code is valid
            country_info = countries.get(country_code)
            return [
                {
                    "valid_from": tag_valid_from,
                    "valid_until": tag_valid_until,
                    "name": f"country:{country_info.alpha2}",
                }
            ]
        except Exception:
            # Invalid country code, we don't set any tag
            return []

    def _parse_db_row(
        self,
        row: bytes,
        tag_valid_from: str,
        tag_valid_until: str,
        asn_cache: dict[int, dict],
    ) -> Iterator[list]:
        """
        Parses a database row and yields the extracted observables.
        """
        try:
            data = json.loads(row.decode("utf-8"))

            asn_number = data["asn"]
            asn_name = data["as_name"]
            country_code = data["country"]

            if asn_number.startswith("AS"):
                asn_number = int(asn_number[2:])

            if asn_name == "":
                asn_name = f"AS{asn_number}"

        except Exception:
            self.log(
                message=f"Found an invalid ASN or country code: {row.decode()}",
                level="error",
            )
            return

        if asn_number == "" or country_code == "":
            # Don't consider not routed IP segment
            return

        tags = self._get_tags(country_code, tag_valid_from, tag_valid_until, row)
        if asn_number in asn_cache:
            autonomous_system = asn_cache[asn_number]
        else:
            autonomous_system = self._get_observable_for_asn(
                asn_cache, asn_number, asn_name
            )

        # yield observables for IP segments
        try:
            result = [autonomous_system]

            ip_start = ipaddress.ip_address(data["start_ip"])
            ip_end = ipaddress.ip_address(data["end_ip"])

            if ip_start.version != ip_end.version:
                raise Exception("Ip start and end are not from the same version")
            if ip_start.version not in (4, 6):
                raise Exception("Only version 4 or 6 of IPs are supported")

            observable_type = f"ipv{ip_start.version}-addr"
            tags.append(
                {
                    "valid_from": tag_valid_from,
                    "valid_until": tag_valid_until,
                    "name": f"asn:{asn_number}",
                }
            )
            for ip_range in ipaddress.summarize_address_range(ip_start, ip_end):
                observable = self._create_observable(observable_type, ip_range, tags)
                relationships = self._create_observable_relationship(
                    observable, autonomous_system
                )
                result += [relationships, observable]

            yield result
        except Exception:
            self.log(
                message=f"Cannot parse provided ip addresses {row.decode()}",
                level="error",
            )

    def _create_observable(
        self,
        observable_type: str,
        ip_range: IPv4Network | IPv6Network,
        tags: list,
    ) -> dict:
        return {
            "type": observable_type,
            "id": f"{observable_type}--{str(uuid.uuid4())}",
            "value": str(ip_range),
            "x_inthreat_tags": tags,
            "x_inthreat_sources_refs": [self.identity["id"]],
        }

    def _create_observable_relationship(
        self, observable: dict, autonomous_system: dict
    ) -> dict:
        return {
            "id": f"observable-relationship--{uuid.uuid4()}",
            "type": "observable-relationship",
            "source_ref": observable["id"],
            "target_ref": autonomous_system["id"],
            "x_inthreat_sources_refs": [self.identity["id"]],
            "relationship_type": "belongs-to",
        }

    def create_event_for_chunk(
        self, location_chunk_info: tuple[list[dict], int]
    ) -> None:
        location_chunk = location_chunk_info[0]
        offset = location_chunk_info[1]

        # Add identity of the service to the bundle
        location_chunk.append(self.identity)
        chunk_size = len(location_chunk)
        file_path = write(
            "observables.json", json.dumps(location_chunk), data_path=self.data_path
        )
        directory = file_path.parent.as_posix()

        self.send_event(
            event_name=f"IPINFO.IO List Chunk {offset}-{offset+chunk_size}",
            event=dict(
                file_path="observables.json", chunk_offset=offset, chunk_size=chunk_size
            ),
            directory=directory,
            remove_directory=True,
        )
