"""Entry point for Check Point Harmony."""

from connectors import CheckpointModule
from connectors.checkpoint_harmony_mobile import CheckpointHarmonyMobileConnector

if __name__ == "__main__":
    module = CheckpointModule()
    module.register(CheckpointHarmonyMobileConnector, "checkpoint_harmony_mobile")
    module.run()
