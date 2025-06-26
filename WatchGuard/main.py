from watchguard import WatchGuardModule
from watchguard.epdr_connector import WatchGuardEpdrConnector

if __name__ == "__main__":
    module = WatchGuardModule()

    module.register(WatchGuardEpdrConnector, "watchguard_epdr")

    module.run()
