import orjson
from functools import cached_property

from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google_module.base import GoogleTrigger
from google_module.metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS

from pydantic import BaseModel
from sekoia_automation.storage import PersistentJSON

from requests.exceptions import HTTPError
from urllib3.exceptions import HTTPError as BaseHTTPError


class GoogleReportsConfig(BaseModel):
    admin_mail: str
    intake_key: str
    frequency: int = 20
    chunk_size: int = 1000


class GoogleReports(GoogleTrigger):

    """
    Connect to Google Reports API and return the results

    Good to know : This's the parent class for all other Google reports applications classes
    """

    configuration: GoogleReportsConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.applicationName = ""
        self.from_date = self.most_recent_date_seen
        self.service_account_path = self.CREDENTIALS_PATH
        self.scopes = []
        self.events_sum = 0

    @property
    def most_recent_date_seen(self):
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last day
            if most_recent_date_seen_str is None:
                return now - timedelta(days=1)

            # parse the most recent date seen
            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            # We don't retrieve messages older than almost 6 months
            six_months = now - timedelta(days=180)
            if most_recent_date_seen < six_months:
                most_recent_date_seen = six_months

            return most_recent_date_seen

    @most_recent_date_seen.setter
    def most_recent_date_seen(self, recent_date):
        most_recent_date_seen = recent_date
        self.from_date = most_recent_date_seen
        with self.context as cache:
            cache["most_recent_date_seen"] = most_recent_date_seen.strftime("%Y-%m-%dT%H:%M:%SZ")

    @cached_property
    def pagination_limit(self):
        return max(self.configuration.chunk_size, 1000)

    def run(self):
        self.log(
            message=f"Starting Google Reports api for {self.applicationName} application at {self.from_date.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            level="info",
        )

        try:
            while self.is_running:
                start = time.time()

                try:
                    self.get_reports_events()

                except HTTPError | BaseHTTPError as ex:
                    self.log_exception(ex, message="Failed to get next batch of events")
                except Exception as ex:
                    self.log_exception(ex, message="An unknown exception occurred")
                    raise

                # compute the duration of the last events fetching
                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                # Compute the remaining sleeping time
                delta_sleep = self.configuration.frequency - duration
                # if greater than 0, sleep
                if delta_sleep > 0:
                    time.sleep(delta_sleep)

        finally:
            self.log(
                message="Failed to forward events from Google Reports API",
                level="info",
            )

    def get_build_object(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_path, scopes=self.scopes
        )
        delegated_credentials = credentials.with_subject(self.configuration.admin_mail)

        reports_service = build("admin", "reports_v1", credentials=delegated_credentials)

        return reports_service

    def get_activities(self):
        reports_service = self.get_build_object()

        self.log(message=f"Start requesting the Google reports with credential object created", level="info")

        activities = (
            reports_service.activities()
            .list(
                userKey="all",
                applicationName=self.applicationName,
                maxResults=self.pagination_limit,
                startTime=self.from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            .execute()
        )

        return activities

    def get_next_activities(self, next_key):
        reports_service = self.get_build_object()

        self.log(message=f"Start requesting the Goole reports with credential object created", level="info")

        activities = (
            reports_service.activities()
            .list(
                userKey="all",
                applicationName=self.applicationName,
                maxResults=self.pagination_limit,
                pageToken=next_key,
                startTime=self.from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            .execute()
        )

        return activities

    def get_next_activities_with_next_key(self, next_key):
        while next_key:
            grouped_data = []
            response_next_page = self.get_next_activities(next_key)

            next_page_items = response_next_page.get("items", [])
            recent_date = next_page_items[0].get("id").get("time")
            self.most_recent_date_seen = isoparse(recent_date)
            grouped_data.extend(next_page_items)
            self.log(message=f"Sending other batches of {len(grouped_data)} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(grouped_data))
            self.push_events_to_intakes(events=grouped_data)
            self.events_sum += len(grouped_data)
            next_key = response_next_page.get("nextPageToken")

    def get_reports_events(self):
        now = datetime.now(timezone.utc)

        self.log(message=f"Creating a google credentials objects", level="info")

        activities = self.get_activities()
        items = activities.get("items", [])
        next_key = activities.get("nextPageToken")

        self.log(message=f"Getting activities with {len(items)} elements", level="info")
        INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(items))

        if len(items) == 0:
            self.most_recent_date_seen = now

        if len(items) > 0:
            recent_date = items[0].get("id").get("time")
            self.most_recent_date_seen = isoparse(recent_date)
            messages = [orjson.dumps(message).decode("utf-8") for message in items]
            self.log(message=f"Sending the first batch of {len(messages)} elements", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
            self.push_events_to_intakes(events=messages)
            self.events_sum += len(messages)

            self.get_next_activities_with_next_key(next_key)

        else:
            self.log(message="No messages to forward", level="info")


class DriveGoogleReports(GoogleReports):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.applicationName = "drive"
        self.scopes = [
            "https://www.googleapis.com/auth/admin.reports.audit.readonly",
            "https://www.googleapis.com/auth/admin.reports.usage.readonly",
        ]
