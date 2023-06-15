import copy
import logging
import os
import re
import uuid
from traceback import format_exc

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from osintcollector.errors import GZipError, MagicLibError, UnzipError
from osintcollector.extract import create_identity, create_observables, magic_data
from osintcollector.scraping import get_scraper
from osintcollector.scraping.errors import ScrapingError, ScrapingRulesError
from sekoia_automation.storage import PersistentJSON, write
from sekoia_automation.trigger import Trigger


class OSINTTrigger(Trigger):
    """
    Trigger that gets the new OSINT events on a regular basis
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Scheduler to fetch the sources
        self._scheduler = BlockingScheduler()

        # Logger
        logging.basicConfig(
            level=logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")),
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        self._logger = logging.getLogger(__name__)

    @property
    def collection(self) -> list:
        return self.configuration.get("collection_sources")

    def _init_sources(self) -> None:
        """
        Initialize the sources collection and the time_sleep.
        It initializes the list that contains timer to fetch sources in the right order.
        Also executes first iteration of each source.
        """
        valid_sources = []

        for source in self.collection:
            # Make sure configuration is correct
            try:
                scraper = get_scraper(source)
                scraper.check_configuration()
                valid_sources.append(source)

                self._scheduler.add_job(
                    self._run,
                    trigger="interval",
                    kwargs={"source": source},
                    name=source.get("name"),
                    seconds=int(source.get("frequency", 3600)),
                )
            except ScrapingRulesError as e:
                self.log(f"Ignoring source {source['name']}: {e.message}", level="warning")
            except Exception:  # pragma: no cover
                self.log(
                    f"Ignoring source {source['name']}: {format_exc()}",
                    level="warning",
                )

        # Run first iteration immediately
        for source in valid_sources:
            self._run(source)

    def run(self) -> None:
        self.log("Starting OSINTCollector trigger")
        self._init_sources()
        self._scheduler.start()
        self.log("Stopping OSINTCollector trigger")

    def _new_observables(self, source: dict, observables: list) -> list:
        """Only return observables that were not returned by the last iteration"""
        if not source.get("cache_results", True):
            return observables

        new_observables = []
        cache_file = re.sub("[^A-Za-z0-9._]", "_", source["url"])

        with PersistentJSON(cache_file, data_path=self._data_path) as cache:
            cache.setdefault("observables", [])

            to_cache = []
            for observable in observables:
                # Copy the object and remove the `date` field
                # Because it will change at each call
                observable_copy = copy.deepcopy(observable)
                for history in observable_copy.get("x_inthreat_history", []):
                    history.pop("date", None)

                for tag in observable_copy.get("x_inthreat_tags", []):
                    tag.pop("valid_from", None)
                    tag.pop("valid_until", None)

                to_cache.append(observable_copy)
                if observable_copy not in cache["observables"]:
                    new_observables.append(observable)

            cache["observables"] = to_cache

        return new_observables

    def _run(self, source) -> None:
        try:
            raw_data = self.__crawl(name=source.get("name"), url=source.get("url"))

            if raw_data:
                try:
                    scraped_data: list[dict] = get_scraper(source).run(data=raw_data)

                    if not scraped_data:
                        self.log(f'No data has been scraped from source {source.get("name")}')
                        return

                    identity = create_identity(source)
                    observables = self._new_observables(source, create_observables(source, identity, scraped_data))

                    if observables:
                        self._send_observables(identity, observables)

                except ScrapingError as e:
                    self.log(
                        f'Error while parsing source {source.get("name")}:\n'
                        f"\tmessage: {e.error}\n"
                        f"\tline_number: {e.line}\n"
                        f"\tline: {e.value}",
                        level="error",
                    )

        except Exception:
            self.log(
                f'Error while parsing source {source.get("name")}: {format_exc()}',
                level="error",
            )

    def _send_observables(self, identity: dict, observables: list):
        """
        Create and send a STIX bundle containing identity and observables
        """
        bundle = {
            "type": "bundle",
            "id": f"bundle--{str(uuid.uuid4())}",
            "objects": [identity] + observables,
        }

        # Save the bundle to a file
        filepath = write("bundle.json", bundle, data_path=self._data_path)

        # Send the event
        plural = "s" if len(observables) > 1 else ""
        name = f"OSINT: {identity['name']}: {len(observables)} observable{plural}"
        self.send_event(
            name,
            {"bundle_path": "bundle.json"},
            filepath.parent.as_posix(),
            remove_directory=True,
        )

    def __crawl(self, name: str, url: str) -> str | None:
        """
        Downloads the raw data from the requested source
        """
        response = requests.get(url, timeout=5)

        if not response.ok:
            self.log(
                f"{name}: HTTP query failed "
                f"(status={response.status_code}, reason={response.reason}, message={response.text})",
                level="error",
            )
            return None

        try:
            data = magic_data(response.content)

        except MagicLibError:
            self.log(f"{name}: Failed to get format type with magic lib", level="error")
            raise

        except UnzipError as err:
            self.log(f"{name} Failed to Unzip data (error={err.exc_info})", level="error")
            raise

        except GZipError as err:
            self.log(f"{name}: Failed to GZip data (error={err.exc_info})", level="error")
            raise

        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8-sig")

            except UnicodeDecodeError:
                try:
                    data = data.decode("latin-1")

                except UnicodeDecodeError:
                    self.log(
                        f"{name}: Failed to decode http response from utf-8 and latin-1",
                        level="error",
                    )
                    raise

        return data
