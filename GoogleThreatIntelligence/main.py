from sekoia_automation.module import Module

from googlethreatintelligence.gti_client import gtiscanfile

if __name__ == "__main__":
    module = Module()

    module.register(gtiscanfile, "scan_file")

    module.run()