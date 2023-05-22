"""
An entrypoint to work with CrowdStrike telemetry events.

Example of usage:
python main.py crowdstrike_telemetry

Also you can set a custom path to the configuration volume:
>>> from sekoia_automation import config
>>> config.VOLUME_PATH = './relative-path-in-current-directory'
"""
from sekoia_automation import config

from crowdstrike_telemetry.crowdstrike import CrowdStrikeTelemetryConnector, CrowdStrikeTelemetryModule
from logger.config import init_logging

config.VOLUME_PATH = "./tests-1"

import os

# os.environ['AWS_ACCESS_KEY_ID'] = 'AKIATA2OLCGEQ32ORE4C'
# os.environ['AWS_SECRET_ACCESS_KEY'] = '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'
# os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


if __name__ == "__main__":
    init_logging()

    module = CrowdStrikeTelemetryModule()
    module.register(CrowdStrikeTelemetryConnector, "crowdstrike_telemetry")
    module.run()
