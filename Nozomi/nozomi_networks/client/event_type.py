from enum import Enum


class EventType(Enum):
    Vulnerabilities = "vulnerabilities"
    Alerts = "alerts"
    WirelessNetworks = "wireless_networks"
    Assets = "assets"
