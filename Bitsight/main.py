from sekoia_automation.loguru.config import init_logging

from connectors import BitsightModule
from connectors.pull_findings_trigger import PullFindingsConnector

if __name__ == "__main__":
    init_logging()
    module = BitsightModule()
    module.register(PullFindingsConnector, "bitsight_findings")
    module.run()
