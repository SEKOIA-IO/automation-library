"""Contains schemas to work with log file."""

from pydantic import BaseModel


class EventLogFile(BaseModel):
    """
    Salesforce EventLogFile entity with ONLY useful fields for connector.

    All existed fields you can find here:
    https://developer.salesforce.com/docs/atlas.en-us.242.0.object_reference.meta/object_reference/sforce_api_objects_eventlogfile.htm
    https://developer.salesforce.com/docs/atlas.en-us.242.0.api_rest.meta/api_rest/dome_event_log_file_query.htm
    """

    Id: str
    EventType: str
    LogFile: str
    LogDate: str
    CreatedDate: str
    LogFileLength: float


class SalesforceEventLogFilesResponse(BaseModel):
    """Salesforce EventLogFile REST response."""

    totalSize: int
    done: bool
    records: list[EventLogFile]
