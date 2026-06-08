from functools import cached_property

from netskope_modules.connector_pull_events_v2 import NetskopeEventConnector
from netskope_modules.types import NetskopeAlertType, NetskopeEventType


class NetskopeSecurityCheckConnector(NetskopeEventConnector):
    """
    Fetches Netskope sandbox / security-check alerts only.

    Netskope API references:
    - https://docs.netskope.com/en/using-the-rest-api-v2-dataexport-iterator-endpoints/
    - https://docs.netskope.com/en/rest-api-events-and-alerts-response-descriptions/
    """

    @cached_property
    def dataexports(self) -> list[tuple[NetskopeEventType, NetskopeAlertType | None]]:
        return [
            (NetskopeEventType.ALERT, NetskopeAlertType.MALWARE),
            (NetskopeEventType.ALERT, NetskopeAlertType.MALSITE),
            (NetskopeEventType.ALERT, NetskopeAlertType.DLP),
        ]
