#!/usr/bin/env python3
"""
Simple TheHive Alert Connector
- Minimal wrapper around thehive4py Alert actions
- Centralizes API initialization
- Adds basic error handling and logging
"""

import logging
from typing import Optional, Dict, List

from thehive4py import TheHiveApi
from thehive4py.errors import TheHiveError
from thehive4py.types.comment import InputComment, InputUpdateComment, OutputComment

# Optional imports for typed input objects (fallback to dict if missing)
try:
    from thehive4py.types.alert import InputAlert, InputUpdateAlert, InputPromoteAlert
    from thehive4py.types.observable import InputObservable
    from thehive4py.types.procedure import InputProcedure
except ImportError:
    InputAlert = dict
    InputUpdateAlert = dict
    InputPromoteAlert = dict
    InputObservable = dict
    InputProcedure = dict


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger("hive.alert.connector")


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