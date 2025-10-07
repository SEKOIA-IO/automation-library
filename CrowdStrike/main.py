"""
An entrypoint to work with CrowdStrike telemetry events.
"""

from connectors import AwsModule

from crowdstrike_telemetry.pull_telemetry_events import CrowdStrikeTelemetryConnector

if __name__ == "__main__":
    module = AwsModule()
    module.register(CrowdStrikeTelemetryConnector, "crowdstrike_telemetry")
    module.run()
