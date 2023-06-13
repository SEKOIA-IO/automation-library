"""
A trigger to download IPtoASN database
"""

import gzip
import ipaddress
import json
import logging
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from io import BytesIO
from ipaddress import IPv4Network, IPv6Network

import requests
from iso3166 import countries
from sekoia_automation.trigger import Trigger

from iptoasn.utils import datetime_to_str


class TriggerFetchIPtoASNDatabase(Trigger):
    MAX_HOUR_TAG_VALID_FOR = 15 * 24
    database_urls = [
        "https://iptoasn.com/data/ip2asn-v4.tsv.gz",
        "https://iptoasn.com/data/ip2asn-v6.tsv.gz",
    ]

    @property
    def identity(self):
        return {
            "id": "identity--9b3b35de-7606-4644-84be-3c68da7d3b99",
            "type": "identity",
            "name": "iptoasn.com",
            "description": "iptoasn.com is a service that maps IP adresses to their Autonomous System Number",
        }

    @property
    def interval(self):
        return self.configuration.get("interval", 24) * 3600

    def run(self):
        """
        Entrypoint of the trigger
        """
        self.log("Starting IPtoASN trigger")
        try:
            while True:
                self._fetch_database()
                logging.debug(f"Sleeping for {self.interval} seconds")
                time.sleep(self.interval)
        finally:
            self.log("IPtoASN trigger is stopping")

    def _fetch_database(self):
        """
        This method downloads the IP-Country database
        and create events in chunks to forward its content
        """
        chunks = 0
        for location_chunk_info in self.build_chunks(
            generator=self.get_iptoasn_database(),
            chunk_size=self.configuration.get("chunk_size", 10000),
        ):
            self.create_event_for_chunk(location_chunk_info)
            chunks += 1
        self.log(f"Sent {chunks} chunk events to the API")

    def create_event_for_chunk(self, location_chunk_info: tuple[list[dict], int]) -> None:
        location_chunk = location_chunk_info[0]
        offset = location_chunk_info[1]

        # Add identity of the service to the bundle
        location_chunk.append(self.identity)

        work_dir = self._data_path.joinpath("iptoasn_chunks").joinpath(str(uuid.uuid4()))
        chunk_path = work_dir.joinpath("observables.json")
        work_dir.mkdir(parents=True, exist_ok=True)
        with chunk_path.open("w") as fp:
            fp.write(json.dumps(location_chunk))

        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(chunk_path.relative_to(work_dir))
        chunk_size = len(location_chunk)
        self.send_event(
            event_name=f"IPTOASN List Chunk {offset}-{offset+chunk_size}",
            event=dict(file_path=file_path, chunk_offset=offset, chunk_size=chunk_size),
            directory=directory,
            remove_directory=True,
        )

    def build_chunks(self, generator: Iterator[list], chunk_size: int) -> Iterator[tuple[list[dict], int]]:
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

    def get_iptoasn_database(self) -> Iterator[list]:
        for url in self.database_urls:
            response = requests.get(url, stream=True)
            if not response.ok:
                logging.error(f"Server answered with {response.status_code}")
                return

            # establishes validity timeframe for produced observables
            #
            # a tag is valid for the (refresh interval * 10) to support errors
            # but cannot be higher than the MAX_HOUR_TAG_VALID_HOUR
            tag_valid_for: int = min(self.MAX_HOUR_TAG_VALID_FOR, self.configuration.get("interval", 24) * 10)
            now: datetime = datetime.utcnow()
            tag_valid_from: str = datetime_to_str(now)
            tag_valid_until: str = datetime_to_str(now + timedelta(hours=tag_valid_for))
            asn_cache: dict[int, dict] = dict()
            with gzip.open(BytesIO(response.content), mode="r") as gz:
                for row in gz.readlines():
                    yield from self._parse_db_row(row, tag_valid_from, tag_valid_until, asn_cache)

    def _get_tags(self, country_code: str, tag_valid_from: str, tag_valid_until: str, row: bytes) -> list:
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

    def _get_observable_for_asn(self, asn_cache: dict, asn_number: int, asn_name: str, tags: list) -> dict:
        asn_cache[asn_number] = {
            "type": "autonomous-system",
            "id": f"autonomous-system--{str(uuid.uuid4())}",
            "number": asn_number,
            "name": asn_name,
            "x_inthreat_tags": tags.copy(),
            "x_inthreat_sources_refs": [self.identity["id"]],
        }
        return asn_cache[asn_number]

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

    def _create_observable_relationship(self, observable: dict, autonomous_system: dict) -> dict:
        return {
            "id": f"observable-relationship--{uuid.uuid4()}",
            "type": "observable-relationship",
            "source_ref": observable["id"],
            "target_ref": autonomous_system["id"],
            "x_inthreat_sources_refs": [self.identity["id"]],
            "relationship_type": "belongs-to",
        }

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
        data = row.strip().split(b"\t")
        if len(data) != 5:
            self.log(
                message=f"Invalid row found in downloaded database, row={row.decode()}",
                level="warning",
            )
            return

        try:
            asn_number = int(data[2].decode("utf-8"))
            asn_name = data[4].decode("utf-8")
            country_code = data[3].decode("utf-8")
        except Exception:
            self.log(
                message=f"Found an invalid ASN or country code: {row.decode()}",
                level="error",
            )
            return

        if asn_number == 0 or country_code == "None":
            # Don't consider not routed IP segment
            return

        tags = self._get_tags(country_code, tag_valid_from, tag_valid_until, row)

        if asn_number in asn_cache:
            autonomous_system = asn_cache[asn_number]
        else:
            autonomous_system = self._get_observable_for_asn(asn_cache, asn_number, asn_name, tags)

        # yield observables for IP segments
        try:
            result = [autonomous_system]

            ip_start = ipaddress.ip_address(data[0].decode("utf-8"))
            ip_end = ipaddress.ip_address(data[1].decode("utf-8"))

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
                relationships = self._create_observable_relationship(observable, autonomous_system)
                result += [relationships, observable]

            yield result
        except Exception:
            self.log(
                message=f"Cannot parse provided ip addresses {row.decode()}",
                level="error",
            )
