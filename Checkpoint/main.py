"""Entry point for Check Point Harmony."""
from connectors import CheckpointModule
from connectors.checkpoint_harmony import CheckpointHarmonyConnector

if __name__ == "__main__":
    module = CheckpointModule()
    module.register(CheckpointHarmonyConnector, "checkpoint_harmony")
    module.run()
