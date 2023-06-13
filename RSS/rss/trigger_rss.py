import re
import shelve
import uuid
from pathlib import Path

import feedparser
import orjson
from apscheduler.schedulers.blocking import BlockingScheduler
from feedparser import FeedParserDict
from sekoia_automation.trigger import Trigger

from rss.errors import MalFormedXMLError
from rss.settings import get_settings


class RSSTrigger(Trigger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._rsscache: dict[str, list[dict]] = {"items": []}

    def run(self) -> None:  # pragma: no cover
        self.log("Trigger starting")
        try:
            self._schedule_feeds()
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            if self._scheduler.running:
                self._scheduler.shutdown()
        finally:
            self.log("Trigger stopping")

    def _schedule_feeds(self) -> None:
        self._scheduler = BlockingScheduler()

        for feed_configuration in self.configuration.get("feeds", []):
            url = feed_configuration.get("url")

            if url:
                frequency = int(feed_configuration.get("frequency", 300))
                strict = bool(feed_configuration.get("strict", False))
                to_file = bool(feed_configuration.get("to_file", False))

                self._scheduler.add_job(
                    self._run,
                    kwargs={"url": url, "strict": strict, "to_file": to_file},
                    trigger="interval",
                    seconds=frequency,
                )

    def _get_feed_content(self, url: str, cache: shelve.Shelf, strict: bool = False) -> FeedParserDict:
        feed: FeedParserDict = feedparser.parse(url, etag=cache.get("etag"), modified=cache.get("modified"))

        if feed.bozo == 1 and strict:
            self.log("Can't parse the RSS feed", level="error")
            raise MalFormedXMLError()

        if feed.get("etag"):
            cache["etag"] = feed.etag

        if feed.get("modified"):
            cache["modified"] = feed.modified

        return feed

    def _get_cache(self, filename: str) -> Path:
        base = get_settings().cache_dir
        base.mkdir(parents=True, exist_ok=True)
        return base / filename

    def _run(self, url: str, strict: bool = False, to_file: bool = False) -> None:
        cache_file = re.sub("[^A-Za-z0-9._]", "_", url)
        with shelve.open(self._get_cache(cache_file).as_posix()) as cache:
            feed = self._get_feed_content(url, cache, strict)

            source = self._format_source(feed.feed)

            last_update = None

            for item in feed.entries:
                new_item = False

                if cache.get("last_update") and item.get("published_parsed"):
                    if item.published_parsed > cache["last_update"]:
                        new_item = True
                elif cache.get("last_update") and item.get("updated_parsed"):
                    if item.updated_parsed > cache["last_update"]:
                        new_item = True
                else:
                    new_item = True

                if new_item:
                    formatted = self._format_item(item)
                    event: dict = {"source": source, "item": formatted}
                    self._send_event(url, event, to_file)

                    if item.get("published_parsed"):
                        if last_update is None or item.published_parsed > last_update:
                            last_update = item.published_parsed
                    elif item.get("updated_parsed"):
                        if last_update is None or item.updated_parsed > last_update:
                            last_update = item.updated_parsed

            if last_update:
                cache["last_update"] = last_update

    def _format_source(self, feed: dict):
        fields = ["title", "subtitle", "link", "language", "author", "publisher"]
        return {key: value for key, value in feed.items() if key in fields}

    def _format_item(self, item: dict) -> dict:
        res = {
            "title": item["title"],
            "link": item["link"],
            "published": item.get("published", item.get("updated")),
            "description": item["summary"],
        }
        if "author" in item:
            res["author"] = item["author"]
        return res

    def _send_event(self, url, event: dict, to_file: bool):
        self.log(f"Sending new event for feed {url}", level="debug")
        event_name = f"RSS feed {url}"
        if not to_file:
            return self.send_event(event_name=event_name, event=event)

        # Save event in file
        work_dir = self._data_path.joinpath("rss_events").joinpath(str(uuid.uuid4()))
        work_dir.mkdir(parents=True, exist_ok=True)

        event_path = work_dir.joinpath("event.json")
        with event_path.open("w") as fp:
            fp.write(orjson.dumps(event).decode("utf-8"))

        # Send event
        directory = str(work_dir.relative_to(self._data_path))
        file_path = str(event_path.relative_to(work_dir))
        self.send_event(
            event_name=event_name,
            event=dict(event_path=file_path),
            directory=directory,
            remove_directory=True,
        )
