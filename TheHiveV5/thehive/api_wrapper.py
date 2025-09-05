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


class HiveConnector:
    """
    Minimal TheHive Alert Connector.
    Usage:
        connector = HiveConnector("http://localhost:9000", "APIKEY123")
        res = connector.alert_get("ALERT-ID")
    """

    def __init__(self, url: str, api_key: str):
        if not api_key:
            raise ValueError("API key is required")

        self.api = TheHiveApi(url=url, apikey=api_key)

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
    def alert_create(self, body: InputAlert, attachment_map: Optional[Dict[str, str]] = None):
        return self._safe_call(self.api.alert.create, alert=body, attachment_map=attachment_map)

    def alert_get(self, alert_id: str):
        return self._safe_call(self.api.alert.get, alert_id=alert_id)

    def alert_delete(self, alert_id: str):
        return self._safe_call(self.api.alert.delete, alert_id=alert_id)

    def alert_update(self, alert_id: str, fields: InputUpdateAlert):
        return self._safe_call(self.api.alert.update, alert_id=alert_id, fields=fields)

    def alert_promote_to_case(self, alert_id: str, fields: Optional[InputPromoteAlert] = None):
        return self._safe_call(self.api.alert.promote_to_case, alert_id=alert_id, fields=fields or {})

    def alert_follow(self, alert_id: str):
        return self._safe_call(self.api.alert.follow, alert_id=alert_id)

    def alert_unfollow(self, alert_id: str):
        return self._safe_call(self.api.alert.unfollow, alert_id=alert_id)

    def alert_merge_into_case(self, alert_id: str, case_id: str):
        return self._safe_call(self.api.alert.merge_into_case, alert_id=alert_id, case_id=case_id)

    def alert_import_into_case(self, alert_id: str, case_id: str):
        return self._safe_call(self.api.alert.import_into_case, alert_id=alert_id, case_id=case_id)

    def alert_get_similar_observables(self, alert_id: str, alert_or_case_id: str):
        return self._safe_call(self.api.alert.get_similar_observables,
                               alert_id=alert_id, alert_or_case_id=alert_or_case_id)

    def alert_add_attachment(self, alert_id: str, attachment_paths: List[str], can_rename: bool = True):
        return self._safe_call(self.api.alert.add_attachment,
                               alert_id=alert_id, attachment_paths=attachment_paths, can_rename=can_rename)

    def alert_delete_attachment(self, alert_id: str, attachment_id: str):
        return self._safe_call(self.api.alert.delete_attachment,
                               alert_id=alert_id, attachment_id=attachment_id)

    def alert_download_attachment(self, alert_id: str, attachment_id: str, download_path: str):
        return self._safe_call(self.api.alert.download_attachment,
                               alert_id=alert_id, attachment_id=attachment_id, attachment_path=download_path)

    def alert_create_observable(self, alert_id: str, observable: InputObservable, observable_path: Optional[str] = None):
        return self._safe_call(self.api.alert.create_observable,
                               alert_id=alert_id, observable=observable, observable_path=observable_path)

    def alert_find(self, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find, filters=filters, sortby=sortby, paginate=paginate)

    def alert_count(self, filters=None):
        return self._safe_call(self.api.alert.count, filters=filters)

    def alert_find_observables(self, alert_id: str, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find_observables,
                               alert_id=alert_id, filters=filters, sortby=sortby, paginate=paginate)

    def alert_find_comments(self, alert_id: str, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find_comments,
                               alert_id=alert_id, filters=filters, sortby=sortby, paginate=paginate)

    def alert_create_procedure(self, alert_id: str, procedure: InputProcedure):
        return self._safe_call(self.api.alert.create_procedure, alert_id=alert_id, procedure=procedure)

    def alert_find_procedures(self, alert_id: str, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find_procedures,
                               alert_id=alert_id, filters=filters, sortby=sortby, paginate=paginate)

    def alert_find_attachments(self, alert_id: str, filters=None, sortby=None, paginate=None):
        return self._safe_call(self.api.alert.find_attachments,
                               alert_id=alert_id, filters=filters, sortby=sortby, paginate=paginate)


# ---------------------- Example usage ----------------------
if __name__ == "__main__":
    connector = HiveConnector("http://localhost:9000", "Yta77NdpXNZLnsBZv3VQQuminbBFre6/")

    # Example: Get an alert
    try:
        alert = connector.alert_find()
        #alert = connector.alert_update("~4231176", {
        #        "title": "My updated alert",
        #        "tags": ["my-tag"],
        #    },
        #)
        print(alert)
        # Example: Add multiple observables to an alert
        observables = [
            {"dataType": "ip", "data": "192.168.1.100"},
            {"dataType": "domain", "data": "phishing-site.com"},
            {"dataType": "url", "data": "http://malicious.example/path"}
        ]

        result = connector.alert_add_observables("~4231176", observables)
        print("Observables added:", result)

    except Exception as e:
        print("Error:", e)
