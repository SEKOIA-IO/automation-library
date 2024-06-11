from mimecast_modules import MimecastModule
from mimecast_modules.connector_mimecast_siem import MimecastSIEMConnector

if __name__ == "__main__":
    module = MimecastModule()
    module.register(MimecastSIEMConnector, "mimecast_email_security")
    module.run()
