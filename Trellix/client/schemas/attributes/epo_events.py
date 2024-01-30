"""
Models for epo events attributes.

https://developer.manage.trellix.com/mvision/apis/v2-events
"""

from datetime import datetime

from pydantic import BaseModel


class EpoEventAttributes(BaseModel):
    """Dto for epo event attributes."""

    timestamp: datetime | None = None
    autoguid: str | None = None
    detectedutc: str | None = None
    receivedutc: str | None = None
    agentguid: str | None = None
    analyzer: str | None = None
    analyzername: str | None = None
    analyzerversion: str | None = None
    analyzerhostname: str | None = None
    analyzeripv4: str | None = None
    analyzeripv6: str | None = None
    analyzermac: str | None = None
    analyzerdatversion: str | None = None
    analyzerengineversion: str | None = None
    analyzerdetectionmethod: str | None = None
    sourcehostname: str | None = None
    sourceipv4: str | None = None
    sourceipv6: str | None = None
    sourcemac: str | None = None
    sourceusername: str | None = None
    sourceprocessname: str | None = None
    sourceurl: str | None = None
    targethostname: str | None = None
    targetipv4: str | None = None
    targetipv6: str | None = None
    targetmac: str | None = None
    targetusername: str | None = None
    targetport: str | None = None
    targetprotocol: str | None = None
    targetprocessname: str | None = None
    targetfilename: str | None = None
    threatcategory: str | None = None
    threateventid: int | None = None
    threatseverity: str | None = None
    threatname: str | None = None
    threattype: str | None = None
    threatactiontaken: str | None = None
    threathandled: bool | None = None
    nodepath: str | None = None
    targethash: str | None = None
    sourceprocesshash: str | None = None
    sourceprocesssigned: str | None = None
    sourceprocesssigner: str | None = None
    sourcefilepath: str | None = None
