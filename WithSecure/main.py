from withsecure import WithSecureModule
from withsecure.security_events_connector import SecurityEventsConnector

if __name__ == "__main__":
    module = WithSecureModule()
    module.register(SecurityEventsConnector, "security_events_connector")
    module.run()
