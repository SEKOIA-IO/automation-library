"""Collect reported messages with acknowledged, scoped pagination checkpoints."""

import hashlib
import json
import logging
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from functools import cached_property
from math import ceil
from time import monotonic
from typing import Any
from urllib.parse import quote

from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration, EventType
from tenacity import stop_when_event_set

from . import MicrosoftOutlookModule
from .action_base import MicrosoftGraphActionBase
from .attachments import collect_attachments
from .client import ApiClient
from .client.retry import retry_deadline
from .graph import MailGraph
from .phishing_events import build_evidence_events

logger = logging.getLogger(__name__)


class PhishingReportsConfiguration(DefaultConnectorConfiguration):
    user: str = Field(min_length=1)
    folder: str = "inbox"
    offset_hours: int = Field(default=24, ge=1, le=2160)
    page_size: int = Field(default=25, ge=1, le=100)
    polling_interval: int = Field(default=60, ge=10, le=3600)
    overlap_seconds: int = Field(default=300, ge=0, le=3600)
    mark_as_read: bool = False


class IntakeDeliveryError(RuntimeError):
    """Identify an unacknowledged intake batch separately from Graph collection errors."""


class PhishingReportsConnector(Connector):
    module: MicrosoftOutlookModule
    configuration: PhishingReportsConfiguration

    @cached_property
    def _activity(self) -> dict[str, int]:
        return dict.fromkeys(
            (
                "cycles",
                "events",
                "failures",
                "delivery_failures",
                "submissions",
                "originals",
                "complete",
                "partial",
                "failed",
                "no_embedded_email",
            ),
            0,
        )

    def _report_activity(self, duration: float, delay: int) -> None:
        # Emit one compact connector-log entry per run, including idle runs.
        # Additional per-step details stay in runtime logs to avoid multiplying API logs.
        if not any(self._activity.values()):
            return
        activity = self._activity
        if activity["submissions"]:
            collected = (
                f"{activity['submissions']} submission{'s' if activity['submissions'] != 1 else ''} processed. "
                f"Extraction outcomes: {activity['complete']} complete, {activity['partial']} partial, "
                f"{activity['failed']} failed."
            )
            if activity["no_embedded_email"]:
                collected += f" {activity['no_embedded_email']} without embedded email."
            if activity["failures"]:
                collected += (
                    f" Collection failures: {activity['failures']} "
                    f"(intake delivery: {activity['delivery_failures']}); see error logs."
                )
        elif activity["delivery_failures"]:
            collected = "Intake delivery failed; checkpoint unchanged."
        elif activity["failures"]:
            collected = "Collection failed; see error logs."
        elif activity["events"]:
            collected = "No submissions completed processing."
        else:
            collected = "No new submissions."
        if not self.running:
            schedule = "Connector stopping."
        elif delay:
            schedule = f"Next batch in {delay} seconds."
        else:
            schedule = "Fetching next page now."
        self.log(
            message=f"{collected} Duration: {duration:.1f} seconds. {schedule}",
            level="warning" if activity["failures"] else "info",
        )
        self._activity.update(dict.fromkeys(self._activity, 0))

    @property
    def frequency(self) -> int:
        # The SDK sleeps uninterruptibly when frequency > 0. run() owns our interruptible wait.
        return 0

    @cached_property
    def graph(self) -> MailGraph:
        cfg = self.module.configuration
        session = ApiClient(
            app_id=cfg.client_id,
            tenant_id=cfg.tenant_id,
            app_secret=MicrosoftGraphActionBase._read_client_secret(cfg.client_secret),
        )
        session.headers["Prefer"] = 'IdType="ImmutableId"'
        return MailGraph(session)

    def _retry(self):
        # Keep SDK retry duration and error-specific waits, including future SDK fixes.
        policy = super()._retry()

        def report_retry(state):
            if policy.before_sleep is not None:
                policy.before_sleep(state)
            if state.attempt_number == 1:
                self._intake_retry_pending = True
                exc = state.outcome.exception() if state.outcome else None
                status = getattr(exc, "status_code", None)
                if status is None:
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                reason = f" (HTTP {status})" if status is not None else ""
                self.log(
                    message=f"Intake delivery failed{reason}; retrying in {state.next_action.sleep:g} seconds. "
                    "Checkpoint unchanged.",
                    level="warning",
                )

        return policy.copy(
            sleep=self._stop_event.wait,
            stop=policy.stop | stop_when_event_set(self._stop_event),
            before_sleep=report_retry,
        )

    def push_events_to_intakes(self, events, sync=False):  # noqa: ARG002 - match SDK interface
        # SDK logs upload failures without raising. Require explicit intake acknowledgements.
        event_ids = super().push_events_to_intakes(events, sync=True)
        if len(event_ids) != len(events):
            raise IntakeDeliveryError("Intake did not acknowledge all events; checkpoint must not advance")
        if getattr(self, "_intake_retry_pending", False):
            self.log(message="Event delivery resumed; all events acknowledged by intake", level="info")
            self._intake_retry_pending = False
        self._activity["events"] += len(event_ids)
        logger.info("Intake acknowledged %s events", len(event_ids))
        return event_ids

    def run(self) -> None:
        self.log(
            message=(
                f"Starting phishing report connector; polling interval: {self.configuration.polling_interval} seconds"
            ),
            level="info",
        )
        last_duration = 0.0
        while self.running:
            delay = self.configuration.polling_interval
            cycle_started = monotonic()
            self._activity["cycles"] += 1
            logger.info("Starting phishing report collection cycle")
            try:
                self.next_run()
                self.heartbeat()
                logger.info("Collection cycle completed in %.2f seconds", monotonic() - cycle_started)
                if getattr(self, "_has_more", False):
                    delay = 0
            except Exception as exc:
                self._activity["failures"] += 1
                deadline = retry_deadline(exc)
                if deadline is not None:
                    self._graph_retry_at = deadline
                if isinstance(exc, IntakeDeliveryError):
                    self._activity["delivery_failures"] += 1
                    message = "Failed to deliver events to intake; checkpoint unchanged"
                else:
                    message = "Failed to collect phishing reports; checkpoint unchanged"
                self.log_exception(exc, message=message)
            deadline = getattr(self, "_graph_retry_at", None)
            if deadline is not None:
                delay = max(delay, ceil(deadline - monotonic()))
            last_duration = monotonic() - cycle_started
            if not self.running:
                self._report_activity(last_duration, 0)
                break
            if delay:
                logger.info("Next batch in the future. Waiting %s seconds", delay)
            else:
                logger.info("More pages available. Fetching next batch immediately")
            self._report_activity(last_duration, delay)
            self._stop_event.wait(delay)
        self._report_activity(last_duration, 0)
        self.log(message="Phishing report connector stopped", level="info")

    @property
    def checkpoint_path(self):
        # A changed account/mailbox/folder starts its own state instead of reusing the previous mailbox cursor.
        cfg = self.module.configuration
        scope = json.dumps([cfg.tenant_id, cfg.client_id, self.configuration.user, self.configuration.folder])
        key = hashlib.sha256(scope.encode()).hexdigest()
        return self.data_path / f"phishing-{key}.json"

    def load_checkpoint(self) -> dict[str, Any]:
        if self.checkpoint_path.exists():
            # Corrupt state must surface as a failure rather than silently skipping/replaying a time window.
            state = json.loads(self.checkpoint_path.read_text())
            datetime.fromisoformat(state["cursor"].replace("Z", "+00:00"))
            return state
        cursor = datetime.now(UTC) - timedelta(hours=self.configuration.offset_hours)
        state = {"cursor": cursor.isoformat(), "seen_ids": [], "next_link": None}
        # Anchor the initial window before any external call, without acknowledging messages.
        self.save_checkpoint(state)
        return state

    def save_checkpoint(self, state: dict[str, Any]) -> None:
        temporary = self.checkpoint_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state))
        temporary.replace(self.checkpoint_path)

    def iterate(self) -> Generator[tuple[list[EventType], datetime | None]]:
        state = self.load_checkpoint()
        user = self.configuration.user
        url = state.get("next_link")
        params = None
        cursor = datetime.fromisoformat(state["cursor"].replace("Z", "+00:00"))
        seen = state.get("seen_received", {identifier: state["cursor"] for identifier in state["seen_ids"]})
        lower_bound = cursor - timedelta(seconds=self.configuration.overlap_seconds) if seen else cursor
        if not url:
            folder = self.graph.folder(user, self.configuration.folder)
            url = f"{self.graph.user_path(user)}/mailFolders/{quote(folder['id'], safe='')}/messages"
            params = {
                "$filter": f"receivedDateTime ge {lower_bound.isoformat()}",
                "$orderby": "receivedDateTime asc",
                "$top": self.configuration.page_size,
                "$select": "id,subject,from,sender,replyTo,toRecipients,ccRecipients,bccRecipients,"
                "receivedDateTime,sentDateTime,body,bodyPreview,hasAttachments,isRead,"
                "importance,internetMessageId,internetMessageHeaders,webLink,"
                "conversationId,parentFolderId,flag",
            }
        try:
            payload = self.graph.page(url, params)
        except Exception as exc:
            response = getattr(exc, "response", None)
            if state.get("next_link") and response is not None and response.status_code == 410:
                # Resume from the acknowledged time window if a Graph continuation has expired.
                self.save_checkpoint({**state, "next_link": None})
            raise
        messages = payload.get("value", [])
        logger.info("Fetched %s messages from Microsoft Graph", len(messages))
        events: list[EventType] = []
        page_activity = dict.fromkeys(
            ("submissions", "originals", "complete", "partial", "failed", "no_embedded_email"), 0
        )
        pending_read = []
        skipped = 0
        for message in messages:
            if not self.running:
                return  # Discard unacknowledged work; the previous checkpoint remains authoritative.
            received = datetime.fromisoformat(message["receivedDateTime"].replace("Z", "+00:00"))
            if received < lower_bound or message["id"] in seen:
                skipped += 1
                continue
            event = self.build_event(message)
            attachments, parsed, errors = collect_attachments(
                self.graph,
                user,
                message["id"],
                embedded_only=True,
                raise_retryable=True,
            )
            event.update(
                attachments=attachments, eml_parsed_data=parsed, processing_errors=errors, collection_mailbox=user
            )
            report_events = build_evidence_events(event, scope=self.module.configuration.tenant_id)
            events.extend(report_events)
            page_activity["submissions"] += 1
            page_activity["originals"] += len(parsed)
            for report_event in report_events:
                page_activity[json.loads(report_event)["extraction_status"]] += 1
            cursor = max(cursor, received)
            seen[message["id"]] = received.isoformat()
            if self.configuration.mark_as_read and not message.get("isRead"):
                pending_read.append(message["id"])
        logger.info(
            "Prepared %s new email events; skipped %s previously collected or older messages", len(events), skipped
        )
        if events:
            logger.info("Forwarding %s email events to intake", len(events))
            yield events, cursor.astimezone(UTC).replace(tzinfo=None)
        else:
            logger.info("No new emails found")
        # SDK resumes this generator only after forwarding the yielded batch.
        retain_after = cursor - timedelta(seconds=self.configuration.overlap_seconds)
        seen = {
            identifier: received
            for identifier, received in seen.items()
            if datetime.fromisoformat(received.replace("Z", "+00:00")) >= retain_after
        }
        self.save_checkpoint(
            {
                "cursor": cursor.isoformat(),
                "seen_ids": sorted(seen),
                "seen_received": seen,
                "next_link": payload.get("@odata.nextLink"),
            }
        )
        # Count processed submissions only after delivery and checkpoint persistence.
        # Failed or abandoned pages are retried and must not inflate extraction totals.
        for key, count in page_activity.items():
            self._activity[key] += count
        self._has_more = bool(payload.get("@odata.nextLink"))
        logger.info("Checkpoint saved; more pages: %s", self._has_more)
        for message_id in pending_read:
            try:
                self.graph.json("PATCH", self.graph.message_url(user, message_id), json={"isRead": True})
            except Exception as exc:
                self.log_exception(exc, message="Events delivered but marking a report as read failed")
                deadline = retry_deadline(exc)
                if deadline is not None:
                    self._graph_retry_at = deadline
                    # Delivery and its checkpoint are already committed. Stop optional
                    # mailbox writes and defer every subsequent Graph call instead.
                    break

    @staticmethod
    def build_event(msg: dict) -> dict[str, Any]:
        """Build a normalized event dict from a Graph API message."""
        from_data = (msg.get("from") or {}).get("emailAddress", {})
        sender_data = (msg.get("sender") or {}).get("emailAddress", {})
        headers = {}
        for h in msg.get("internetMessageHeaders") or []:
            headers[h.get("name", "")] = h.get("value", "")

        event: dict[str, Any] = {
            "event_type": "microsoft_graph_mail_phishing_report",
            "id": msg.get("id", ""),
            "subject": msg.get("subject", ""),
            "from_address": from_data.get("address", ""),
            "from_name": from_data.get("name", ""),
            "sender_address": sender_data.get("address", ""),
            "sender_name": sender_data.get("name", ""),
            "reply_to": [r.get("emailAddress", {}).get("address", "") for r in msg.get("replyTo", [])],
            "to_recipients": [r.get("emailAddress", {}).get("address", "") for r in msg.get("toRecipients", [])],
            "cc_recipients": [r.get("emailAddress", {}).get("address", "") for r in msg.get("ccRecipients", [])],
            "bcc_recipients": [r.get("emailAddress", {}).get("address", "") for r in msg.get("bccRecipients", [])],
            "received_datetime": msg.get("receivedDateTime", ""),
            "sent_datetime": msg.get("sentDateTime", ""),
            "body_content_type": (msg.get("body") or {}).get("contentType", ""),
            "body_preview": msg.get("bodyPreview", ""),
            "body_content": (msg.get("body") or {}).get("content", ""),
            "has_attachments": msg.get("hasAttachments", False),
            "is_read": msg.get("isRead", False),
            "importance": msg.get("importance", ""),
            "internet_message_id": msg.get("internetMessageId", ""),
            "internet_message_headers": headers,
            "web_link": msg.get("webLink", ""),
            "conversation_id": msg.get("conversationId", ""),
            "parent_folder_id": msg.get("parentFolderId", ""),
            "flag_status": (msg.get("flag") or {}).get("flagStatus", ""),
            "attachments": [],
            "eml_parsed_data": [],
        }

        return event
