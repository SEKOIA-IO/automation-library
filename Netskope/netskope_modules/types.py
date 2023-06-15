from enum import Enum


class NetskopeEventType(str, Enum):
    ALERT = "alert"
    PAGE = "page"
    APPLICATION = "application"
    INCIDENT = "incident"
    AUDIT = "audit"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"


class NetskopeAlertType(str, Enum):
    DLP = "dlp"
    WATCHLIST = "watchlist"
    CTEP = "ctep"
    COMPROMISEDCREDENTIAL = "compromisedcredential"
    MALSITE = "malsite"
    MALWARE = "malware"
    POLICY = "policy"
    REMEDIATION = "remediation"
    QUARANTINE = "quarantine"
    SECURITYASSESSMENT = "securityassessment"
    UBA = "uba"
