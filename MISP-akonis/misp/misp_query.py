import logging

from pymisp import PyMISP, PyMISPError


class MISPError(Exception):
    pass


class MISPQuery:
    def __init__(self, url, key, verify_ssl=True):
        self._logger = logging.getLogger(__name__)
        self._api = PyMISP(url=url, key=key, ssl=verify_ssl)

    def get_events_starting_from(self, timestamp: float):
        try:
            res = self._api.search(publish_timestamp=timestamp)
        except PyMISPError as ex:
            self._logger.error(f"The MISP server returned the following error: {ex.message}")
            raise MISPError(ex.message)

        if "errors" in res:
            self._logger.error(f"The MISP server returned the following error: {res['errors']}")
            raise MISPError(res["errors"])

        return [item for item in res if "Event" in item]
