#!/usr/bin/env python3
"""
Simple TheHive Alert Connector
- Minimal wrapper around thehive4py Alert actions
- Centralizes API initialization
- Adds basic error handling and logging
"""

import atexit
import hashlib
import logging
import os
import tempfile
from typing import Optional, Dict, List, Any, Union

from thehive4py import TheHiveApi
from thehive4py.errors import TheHiveError

from thehive4py.types.comment import InputComment, InputUpdateComment, OutputComment

# Optional imports for typed input objects (fallback to dict if missing)
try:
    from thehive4py.types.alert import InputAlert, InputUpdateAlert, InputPromoteAlert
    from thehive4py.types.observable import InputObservable
    from thehive4py.types.procedure import InputProcedure
except ImportError:
    InputAlert = dict  # type: ignore[misc,assignment]
    InputUpdateAlert = dict  # type: ignore[misc,assignment]
    InputPromoteAlert = dict  # type: ignore[misc,assignment]
    InputObservable = dict  # type: ignore[misc,assignment]
    InputProcedure = dict  # type: ignore[misc,assignment]


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
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
    "user.name": "hostname",
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

# TLP and PAP level mappings (string to int)
TLP_LEVELS = {
    "CLEAR": 0,
    "WHITE": 0,  # Alias for CLEAR
    "GREEN": 1,
    "AMBER": 2,
    "AMBER+STRICT": 3,
    "RED": 4,
}

PAP_LEVELS = {
    "CLEAR": 0,
    "WHITE": 0,  # Alias for CLEAR
    "GREEN": 1,
    "AMBER": 2,
    "RED": 3,
}


def key_exists(mapping: dict, key_to_check: str) -> bool:
    # ensure type safety with isinstance
    if not isinstance(key_to_check, str):
        raise TypeError("key_to_check must be a string")

    return key_to_check in mapping


# Cache for CA certificate files to avoid creating duplicates
_ca_file_cache: Dict[str, str] = {}
_atexit_registered = False


def _cleanup_ca_files() -> None:
    """Clean up all cached CA certificate files at process exit."""
    global _ca_file_cache
    for ca_file in list(_ca_file_cache.values()):
        try:
            if os.path.exists(ca_file):
                os.unlink(ca_file)
        except OSError:
            logger.warning("Failed to clean up temporary CA file: %s", ca_file)
    _ca_file_cache.clear()


def prepare_verify_param(verify: bool, ca_certificate: Optional[str] = None) -> Union[bool, str]:
    """
    Prepare the verify parameter for requests/thehive4py.

    Args:
        verify: Whether to verify the certificate
        ca_certificate: PEM-encoded CA certificate content (optional)

    Returns:
        - False if verify is False
        - Path to temp CA file if ca_certificate is provided
        - True otherwise (use system CA store)
    """
    global _atexit_registered

    if not verify:
        return False

    if ca_certificate:
        # Treat empty or whitespace-only certificate as no certificate
        ca_certificate = ca_certificate.strip()
        if not ca_certificate:
            return True

        # Normalize line endings to Unix-style for consistent hashing
        ca_certificate = ca_certificate.replace("\r\n", "\n").replace("\r", "\n")

        # Use hash of certificate content as cache key to avoid duplicates
        ca_hash = hashlib.sha256(ca_certificate.encode()).hexdigest()

        # Check cache with existence verification
        if ca_hash in _ca_file_cache:
            cached_path = _ca_file_cache[ca_hash]
            try:
                # Verify file still exists and is readable
                with open(cached_path, "r") as f:
                    f.read(1)
                return cached_path
            except (OSError, IOError):
                # File was deleted or is inaccessible, remove from cache
                del _ca_file_cache[ca_hash]

        # Create new temp file with restricted permissions
        fd, ca_file = tempfile.mkstemp(suffix=".pem", text=True)
        try:
            # Set restrictive permissions (owner read/write only)
            os.chmod(ca_file, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(ca_certificate)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            # Clean up on failure
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(ca_file)
            except OSError:
                pass
            raise

        _ca_file_cache[ca_hash] = ca_file

        # Register cleanup only once
        if not _atexit_registered:
            atexit.register(_cleanup_ca_files)
            _atexit_registered = True

        return ca_file

    return True


class TheHiveConnector:
    """
    Minimal TheHive Alert Connector.
    Usage:
        connector = HiveConnector("http://localhost:9000", "APIKEY123", organisation="YOURORGA")
        res = connector.alert_get("ALERT-ID")
    """

    def __init__(
        self, url: str, api_key: str, organisation: str, verify: bool = True, ca_certificate: Optional[str] = None
    ):
        if not api_key:
            raise ValueError("API key is required")

        verify_param = prepare_verify_param(verify, ca_certificate)
        self.api = TheHiveApi(url=url, apikey=api_key, organisation=organisation, verify=verify_param)

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

    @staticmethod
    def sekoia_to_thehive(events, tlp, pap, ioc) -> List[Dict[str, Any]]:
        # Convert TLP and PAP to integers if they are strings
        if isinstance(tlp, str):
            tlp_int = TLP_LEVELS.get(tlp.upper(), 2)  # Default to AMBER (2) if unknown
            if tlp.upper() not in TLP_LEVELS:
                logging.warning("Unknown TLP level '%s', defaulting to AMBER (2)", tlp)
        else:
            tlp_int = tlp

        if isinstance(pap, str):
            pap_int = PAP_LEVELS.get(pap.upper(), 2)  # Default to AMBER (2) if unknown
            if pap.upper() not in PAP_LEVELS:
                logging.warning("Unknown PAP level '%s', defaulting to AMBER (2)", pap)
        else:
            pap_int = pap

        observables: List[Dict[str, Any]] = []
        for idx, ev in enumerate(events):
            if not isinstance(ev, dict):
                logging.warning("Skipping non-dict event at index %d", idx)
                continue
            for k, v in ev.items():
                if k in SEKOIA_FIELDS:
                    thehive_field = SEKOIA_TO_THEHIVE.get(k, "<unknown>")
                    # Skip observables with unknown data types
                    if thehive_field == "<unknown>":
                        logging.warning("Skipping observable with unknown data type for field '%s'", k)
                        continue
                    # Ensure data is a string
                    if not isinstance(v, str):
                        v = str(v)
                    observable = {
                        "dataType": thehive_field,
                        "data": v,
                        "tlp": tlp_int,
                        "pap": pap_int,
                        "ioc": ioc,
                    }
                    observables.append(observable)
        deduplicated: List[Dict[str, Any]] = []
        for o in observables:
            if o not in deduplicated:
                deduplicated.append(o)
        return deduplicated

    def alert_find(self, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find, filters=filters, sortby=sortby, paginate=paginate)

    def alert_create_observable(
        self,
        alert_id: str,
        observable: InputObservable,
        observable_path: Optional[str] = None,
    ):
        """Create a single observable on an alert."""
        return self._safe_call(
            self.api.alert.create_observable,
            alert_id=alert_id,
            observable=observable,
            observable_path=observable_path,
        )

    def alert_add_observables(self, alert_id: str, observables: List[Dict[str, Any]]) -> Dict[str, List]:
        """
        Bulk add multiple observables to an alert.

        Args:
            alert_id: The alert ID to add observables to
            observables: List of observables to add

        Returns:
            Dict with 'success' and 'failure' lists:
            - 'success': List of successfully created observables
            - 'failure': List of dicts containing failed observable and error message

        Raises:
            TheHiveError: If ALL observables fail to be added
        """

        def _bulk_add():
            results = {"success": [], "failure": []}
            for obs in observables:
                try:
                    result = self.alert_create_observable(alert_id, obs)
                    results["success"].append(result)
                except Exception as e:
                    logger.warning(
                        "Failed to add observable (type=%s, data=%s): %s", obs.get("dataType"), obs.get("data"), e
                    )
                    results["failure"].append({"observable": obs, "error": str(e)})

            # If ALL failed, raise an error
            if not results["success"] and results["failure"]:
                raise TheHiveError("Failed to add any observables")

            return results

        return self._safe_call(_bulk_add)

    def comment_add_in_alert(self, alert_id: str, comment: InputComment):
        """Add a text comment to an alert."""
        return self._safe_call(self.api.comment.create_in_alert, alert_id=alert_id, comment=comment)

    def alert_add_attachment(self, alert_id: str, attachment_paths: List[str], can_rename: bool = True):
        return self._safe_call(
            self.api.alert.add_attachment,
            alert_id=alert_id,
            attachment_paths=attachment_paths,
            can_rename=can_rename,
        )
