from deep_visibility.base import SentinelOneDeepVisibilityModule
from deep_visibility.connector_s3_logs import DeepVisibilityConnector

if __name__ == "__main__":
    module = SentinelOneDeepVisibilityModule()
    module.register(DeepVisibilityConnector, "sentinelone_deep_visibility_consumer")
    module.run()
