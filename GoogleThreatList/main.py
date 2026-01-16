"""
SEKOIA.IO Integration Module
"""

from google_threat_intelligence.trigger_google_threat_intelligence_threat_list_to_ioc_collection import (
    GoogleThreatIntelligenceThreatListToIOCCollectionTrigger,
)
from sekoia_automation.module import Module

if __name__ == "__main__":
    module = Module()
    module.register(
        GoogleThreatIntelligenceThreatListToIOCCollectionTrigger,
        "trigger-google-threat-intelligence-threat-list-to-ioc-collection",
    )
    module.run()
