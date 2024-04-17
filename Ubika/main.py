from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_alerts import (
    UbikaCloudProtectorAlertsConnector,
)

if __name__ == "__main__":
    module = UbikaModule()
    module.register(UbikaCloudProtectorAlertsConnector, "ubika_cloud_protector_alerts")
    module.run()
