"""
An entrypoint to work with CrowdStrike telemetry events.
"""

from crowdstrike_telemetry import CrowdStrikeTelemetryModule
from crowdstrike_telemetry.pull_telemetry_events import CrowdStrikeTelemetryConnector

if __name__ == "__main__":
    module = CrowdStrikeTelemetryModule()
    module.register(CrowdStrikeTelemetryConnector, "crowdstrike_telemetry")
    module.run()
