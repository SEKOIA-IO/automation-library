#!/usr/bin/env python3
"""
Simple TheHive Alert Connector
- Minimal wrapper around thehive4py Alert actions
- Centralizes API initialization
- Adds basic error handling and logging
"""

import logging
from typing import Optional, Dict, List, Any

from thehive4py import TheHiveApi
from thehive4py.errors import TheHiveError

# Optional imports for typed input objects (fallback to dict if missing)
try:
    from thehive4py.types.observable import InputObservable
except ImportError:
    InputObservable = dict


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger("hive.alert.connector")

# ---------- CONFIG ----------

# List of Sekoia fields to attempt to extract (order doesn't matter)
SEKOIA_FIELDS = [
    "url.domain",
    "user.domain",
    "group.domain",
    "host.domain",
    "destination.domain",
    "destination.user.domain",
    "destination.user.group.domain",
    "client.domain",
    "client.user.domain",
    "client.user.group.domain",
    "source.domain",
    "source.user.domain",
    "source.user.group.domain",
    "file.name",
    "dll.hash.md5",
    "dll.hash.sha1",
    "dll.hash.sha256",
    "email.attachments.file.hash.md5",
    "email.attachments.file.hash.sha1",
    "email.attachments.file.hash.sha256",
    "file.hash.md5",
    "file.hash.sha1",
    "file.hash.sha256",
    "process.hash.md5",
    "process.hash.sha1",
    "process.hash.sha256",
    "process.parent.hash.md5",
    "process.parent.hash.sha1",
    "process.parent.hash.sha256",
    "host.hostname",
    "host.name",
    "source.ip",
    "destination.ip",
    "destination.nat.ip",
    "host.ip",
    "client.ip",
    "client.nat.ip",
    "email.sender.address",
    "email.to.address",
    "email.from.address",
    "email.to",
    "email.from",
    "client.user.email",
    "destination.user.email",
    "server.user.email",
    "source.user.email",
    "user.changes.email",
    "user.effective.email",
    "url.path",
    "url.full",
    "url.original",
    "user_agent.original",
    # suggestions:
    "file.path",
    "user.name",
]

# Mapping CSV provided -> dict
SEKOIA_TO_THEHIVE = {
    "url.domain": "domain",
    "user.domain": "domain",
    "group.domain": "domain",
    "host.domain": "domain",
    "destination.domain": "domain",
    "destination.user.domain": "domain",
    "destination.user.group.domain": "domain",
    "client.domain": "domain",
    "client.user.domain": "domain",
    "client.user.group.domain": "domain",
    "source.domain": "domain",
    "source.user.domain": "domain",
    "source.user.group.domain": "domain",
    "file.name": "filename",
    "dll.hash.md5": "hash",
    "dll.hash.sha1": "hash",
    "dll.hash.sha256": "hash",
    "email.attachments.file.hash.md5": "hash",
    "email.attachments.file.hash.sha1": "hash",
    "email.attachments.file.hash.sha256": "hash",
    "file.hash.md5": "hash",
    "file.hash.sha1": "hash",
    "file.hash.sha256": "hash",
    "process.hash.md5": "hash",
    "process.hash.sha1": "hash",
    "process.hash.sha256": "hash",
    "process.parent.hash.md5": "hash",
    "process.parent.hash.sha1": "hash",
    "process.parent.hash.sha256": "hash",
    "url.path": "uri_path",
    "url.full": "url",
    "url.original": "url",
    "user_agent.original": "user-agent",
    "host.hostname": "hostname",
    "host.name": "hostname",
    "source.ip": "ip",
    "destination.ip": "ip",
    "destination.nat.ip": "ip",
    "host.ip": "ip",
    "client.ip": "ip",
    "client.nat.ip": "ip",
    "email.sender.address": "mail",
    "email.to.address": "mail",
    "email.from.address": "mail",
    "email.to": "mail",
    "email.from": "mail",
    "client.user.email": "mail",
    "destination.user.email": "mail",
    "server.user.email": "mail",
    "source.user.email": "mail",
    "user.changes.email": "mail",
    "user.effective.email": "mail",
}

def key_exists(mapping: dict, key_to_check: str) -> bool:
    # ensure type safety with isinstance
    if not isinstance(key_to_check, str):
        raise TypeError("key_to_check must be a string")

    return key_to_check in mapping

class TheHiveConnector:
    """
    Minimal TheHive Alert Connector.
    Usage:
        connector = HiveConnector("http://localhost:9000", "APIKEY123", organisation="YOURORGA")
        res = connector.alert_get("ALERT-ID")
    """

    def __init__(self, url: str, api_key: str, organisation: str):
        if not api_key:
            raise ValueError("API key is required")

        self.api = TheHiveApi(url=url, apikey=api_key, organisation=organisation)

    def _safe_call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except TheHiveError as e:
            logger.error("TheHive API error: %s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error calling TheHive")
            raise

    # ---------------------- Alert actions ----------------------

    def sekoia_to_thehive(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                out: List[Dict[str, Any]] = []
                observables: List[Dict[str, Any]] = []
                #observables = [
                #    {"dataType": "ip", "data": "192.168.1.100"},
                #    {"dataType": "domain", "data": "phishing-site.com"},
                #    {"dataType": "url", "data": "http://malicious.example/path"}
                #]
                for idx, ev in enumerate(data):
                    #print("idx", idx)
                    if not isinstance(ev, dict):
                        logging.warning("Skipping non-dict event at index %d", idx)
                        continue
                    for k, v in ev.items():
                        if key_exists(SEKOIA_FIELDS, k):
                            #print(k, "exists in SEKOIA_FIELDS, with value:", v)
                            thehive_field=SEKOIA_TO_THEHIVE.get(k, "<unknown>")
                            #print("-> Associated TheHive field is", thehive_field)
                            out.append({thehive_field: v})
                            observables.append({"dataType": thehive_field, "data": v})

                return observables
    
    def alert_find(self, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find, filters=filters, sortby=sortby, paginate=paginate)
    
    def alert_create_observable(self, alert_id: str, observable: InputObservable, observable_path: Optional[str] = None):
        """Create a single observable on an alert."""
        return self._safe_call(
            self.api.alert.create_observable,
            alert_id=alert_id, observable=observable, observable_path=observable_path
        )

    def alert_add_observables(self, alert_id: str, observables: List[InputObservable]):
        """Bulk add multiple observables to an alert."""
        return [self.alert_create_observable(alert_id, obs) for obs in observables]
    
    def comment_add_in_alert(self, alert_id: str, comment: str):
        """Add a text comment to an alert."""
        return self._safe_call(self.api.comment.create_in_alert, alert_id=alert_id, comment=comment)
    
    def alert_add_attachment(self, alert_id: str, attachment_paths: List[str], can_rename: bool = True):
        return self._safe_call(
            self.api.alert.add_attachment,
            alert_id=alert_id, attachment_paths=attachment_paths, can_rename=can_rename
        )