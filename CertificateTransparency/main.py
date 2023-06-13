from sekoia_automation.module import Module

from certificatetransparency.triggers.certificate_updated import CertificateUpdatedTrigger

if __name__ == "__main__":
    module = Module()
    module.register(CertificateUpdatedTrigger, "certificate-updated-trigger")
    module.run()
