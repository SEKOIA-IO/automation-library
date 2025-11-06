from sekoia_automation.module import Module

from googlethreatintelligence.get_ioc_report import GTIIoCReport
from googlethreatintelligence.scan_file import GTIScanFile
from googlethreatintelligence.get_comments import GTIGetComments
from googlethreatintelligence.get_file_behaviour import GTIGetFileBehaviour
from googlethreatintelligence.get_passive_dns import GTIGetPassiveDNS
from googlethreatintelligence.get_vulnerability_associations import GTIGetVulnerabilityAssociations
from googlethreatintelligence.get_vulnerability_report import GTIGetVulnerabilityReport
from googlethreatintelligence.scan_url import GTIScanURL

if __name__ == "__main__":
    module = Module()

    #DONE
    module.register(GTIIoCReport, "get_ioc_report")
    module.register(GTIScanFile, "scan_file")
    #TODO
    module.register(GTIGetComments, "get_comments")
    module.register(GTIGetVulnerabilityAssociations, "get_vulnerability_assocations")
    module.register(GTIGetFileBehaviour, "get_file_behaviour")
    module.register(GTIScanURL, "scan_url")
    module.register(GTIGetPassiveDNS, "get_passive_dns")
    module.register(GTIGetVulnerabilityReport, "get_vulnerability_report")

    module.run()