import orjson
from functools import cached_property
from typing import Optional

from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
import time

from enum import Enum
from threading import Event

from google.oauth2 import service_account
from googleapiclient.discovery import build

from google_module.base import GoogleTrigger
from google_module.metrics import FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS
from google_module.timestepper import TimeStepper

from sekoia_automation.storage import PersistentJSON
from sekoia_automation.connector import DefaultConnectorConfiguration

from requests.exceptions import HTTPError
from urllib3.exceptions import HTTPError as BaseHTTPError
from google.auth.exceptions import TransportError
from httplib2.error import ServerNotFoundError


class ApplicationName(str, Enum):
    ACCESS_TRANSPARENCY = "access_transparency"
    ADMIN = "admin"
    CALENDAR = "calendar"
    CHAT = "chat"
    DRIVE = "drive"
    GCP = "gcp"
    GPLUS = "gplus"
    GROUPS = "groups"
    GROUPS_ENTERPRISE = "groups_enterprise"
    JAMBOARD = "jamboard"
    LOGIN = "login"
    MEET = "meet"
    MOBILE = "mobile"
    RULES = "rules"
    SAML = "saml"
    TOKEN = "token"
    USER_ACCOUNTS = "user_accounts"
    CONTEXT_AWARE_ACCESS = "context_aware_access"
    CHROME = "chrome"
    DATA_STUDIO = "data_studio"
    KEEP = "keep"
    VAULT = "vault"


class GoogleReportsConfig(DefaultConnectorConfiguration):
    admin_mail: str
    frequency: int = 60
    application_name: ApplicationName = ApplicationName.LOGIN
    chunk_size: int = 1000
    timedelta: int = 1
    start_time: int = 1


class GoogleReports(GoogleTrigger):
    """
    Connect to Google Reports API and return the results
    """

    configuration: GoogleReportsConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.service_account_path = self.CREDENTIALS_PATH
        self.scopes = [
            "https://www.googleapis.com/auth/admin.reports.audit.readonly",
            "https://www.googleapis.com/auth/admin.reports.usage.readonly",
        ]
        self._stop_event = Event()
        self.from_date = ""

    @property
    def stepper(self):
        now = datetime.now(timezone.utc)

        with self.context as cache:
            app_key_name_in_cache = "most_recent_date_seen_" + self.configuration.application_name.value
            most_recent_date_seen_str = cache.get(app_key_name_in_cache) or cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last day
            if most_recent_date_seen_str is None:
                return TimeStepper.create(
                    self,
                    self.configuration.frequency,
                    self.configuration.timedelta,
                    self.configuration.start_time,
                )

            # parse the most recent date seen
            most_recent_date_seen = isoparse(most_recent_date_seen_str)

            # We don't retrieve messages older than almost 6 months
            six_months_ago = now - timedelta(days=180)
            if most_recent_date_seen < six_months_ago:
                most_recent_date_seen = six_months_ago

            timeshift = timedelta(minutes=self.configuration.timedelta)

            start = most_recent_date_seen
            end = now - timeshift  # set the end of the period to the now minus the temporal shift
            if start > end:
                # this is a case when most_recent_date_seen > now() - timedelta
                start = most_recent_date_seen - timeshift

            return TimeStepper(
                self,
                start,
                end,
                timedelta(seconds=self.configuration.frequency),
                timeshift,
            )

    @stepper.setter
    def stepper(self, recent_date):
        self.from_date = recent_date
        with self.context as cache:
            app_key_name_in_cache = "most_recent_date_seen_" + self.configuration.application_name.value
            cache[app_key_name_in_cache] = self.from_date

    @cached_property
    def pagination_limit(self):
        return max(self.configuration.chunk_size, 1000)

    @cached_property
    def reports_service(self):
        """
        Returns a build object for accessing Google Admin Reports API.
        """
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_path, scopes=self.scopes
        )
        delegated_credentials = credentials.with_subject(self.configuration.admin_mail)

        return build("admin", "reports_v1", credentials=delegated_credentials)

    def stop(self, *args, **kwargs):
        self.log(message="Stopping Google Reports API trigger", level="info")
        super().stop(*args, **kwargs)

    def run(self):
        self.log(
            message=f"Starting Google Reports api for {self.configuration.application_name.value} application at {self.stepper.start.isoformat()}",
            level="info",
        )

        try:
            for start, end in self.stepper.ranges():
                # check if the trigger should stop
                if self._stop_event.is_set():
                    break

                duration_start = time.time()

                try:
                    self.get_reports_events(start, end)
                except (HTTPError, BaseHTTPError) as ex:
                    self.log_exception(ex, message="Failed to get next batch of events")
                except Exception as ex:
                    self.log(
                        message=f"An unknown exception occurred : {str(ex)}",
                        level="error",
                    )
                    raise

                # Save the most recent date seen
                self.stepper = end.isoformat()
                self.log(message=f"Changing recent date in get reports events to  {end.isoformat()}", level="info")

                # compute the duration of the last events fetching
                duration = int(time.time() - duration_start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

        finally:
            self.log(
                message="Failed to forward events from Google Reports API",
                level="info",
            )

    def get_activities(self, start: str, end: str, next_key: Optional[str] = None):
        message_without_nk = f"Initiating Google reports request using the created credential object."
        message_with_nk = f"Initiating Google reports request using the created credential object. Next_key {next_key} included for pagination."
        log_message = message_with_nk if next_key else message_without_nk
        self.log(message=log_message, level="info")

        try:
            activities = (
                self.reports_service.activities()
                .list(
                    userKey="all",
                    applicationName=self.configuration.application_name.value,
                    maxResults=self.pagination_limit,
                    startTime=start,
                    endTime=end,
                    pageToken=next_key,
                )
                .execute()
            )

            return activities

        except (TransportError, ServerNotFoundError, OSError, BrokenPipeError) as ex:
            self.log(message=f"Can't reach the google api server during processing of request: {ex}", level="warning")

    def get_reports_with_nk(self, start: str, end: str, next_key: str):
        const_next_key = next_key
        self.log(
            message=f"Start looping for all next activities with the first next key {const_next_key}",
            level="info",
        )
        while const_next_key:
            response_next_page = self.get_activities(start, end, const_next_key) or {}
            next_page_items = response_next_page.get("items", [])
            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(next_page_items))

            if next_page_items:
                next_messages = [orjson.dumps(message).decode("utf-8") for message in next_page_items]
                self.log(message=f"Sending other batches of {len(next_messages)} messages", level="info")
                OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(next_messages))
                self.push_events_to_intakes(events=next_messages)

                const_next_key = response_next_page.get("nextPageToken", "")
                self.log(
                    message=f"Updated nextKey to the new value: {const_next_key}",
                    level="info",
                )

            else:
                const_next_key = ""
                self.log(message=f"There's no items even if there's a next key!!", level="info")

    def get_reports_events(self, start: datetime, end: datetime):
        self.log(message=f"Creating a google credentials objects", level="info")
        start_isoformat, stop_isoformat = start.isoformat(), end.isoformat()
        activities = self.get_activities(start_isoformat, stop_isoformat) or {}
        items, next_key = activities.get("items", []), activities.get("nextPageToken")

        self.log(message=f"Getting activities with {len(items)} elements", level="info")
        INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(items))

        if len(items) > 0:
            messages = [orjson.dumps(message).decode("utf-8") for message in items]
            self.log(message=f"Sending the first batch of {len(messages)} messages", level="info")
            OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(messages))
            self.push_events_to_intakes(events=messages)

            if next_key:
                self.get_reports_with_nk(start_isoformat, stop_isoformat, next_key)

        else:
            self.log(message="No messages to forward", level="info")
