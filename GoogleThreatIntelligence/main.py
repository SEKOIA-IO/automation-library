from sekoia_automation.module import Module

from googlethreatintelligence.actions.get_ioc_report import GTIIoCReport
from googlethreatintelligence.actions.scan_file import GTIScanFile
from googlethreatintelligence.actions.get_comments import GTIGetComments
from googlethreatintelligence.actions.get_file_behaviour import GTIGetFileBehaviour
from googlethreatintelligence.actions.get_passive_dns import GTIGetPassiveDNS
from googlethreatintelligence.actions.get_vulnerability_associations import GTIGetVulnerabilityAssociations
from googlethreatintelligence.actions.get_vulnerability_report import GTIGetVulnerabilityReport
from googlethreatintelligence.actions.scan_url import GTIScanURL
from googlethreatintelligence.triggers.threat_list_to_ioc_collection import (
    GoogleThreatIntelligenceThreatListToIOCCollectionTrigger,
)

if __name__ == "__main__":
    module = Module()

    module.register(GTIIoCReport, "get_ioc_report")
    module.register(GTIScanFile, "scan_file")
    module.register(GTIGetComments, "get_comments")
    module.register(GTIGetVulnerabilityAssociations, "get_vulnerability_assocations")
    module.register(GTIGetFileBehaviour, "get_file_behaviour")
    module.register(GTIScanURL, "scan_url")
    module.register(GTIGetPassiveDNS, "get_passive_dns")
    module.register(GTIGetVulnerabilityReport, "get_vulnerability_report")
    module.register(
        GoogleThreatIntelligenceThreatListToIOCCollectionTrigger,
        "trigger-google-threat-intelligence-threat-list-to-ioc-collection",
    )

    module.run()
