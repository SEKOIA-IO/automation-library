from lookout_modules import LookoutModule
from lookout_modules.connector_mobile_endpoint_security import MobileEndpointSecurityConnector

if __name__ == "__main__":
    module = LookoutModule()
    module.register(MobileEndpointSecurityConnector, "lookout_mes")
    module.run()
