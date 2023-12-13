from sekoia_automation.module import Module

from google_module.big_query import BigQueryAction
from google_module.google_reports import GoogleReports
from google_module.pubsub import PubSub
from google_module.pubsub_lite import PubSubLite


if __name__ == "__main__":
    module = Module()

    module.register(BigQueryAction, "run-bigquery-query")
    module.register(PubSub, "run-pubsub")
    module.register(GoogleReports, "run-google_reports_trigger")
    module.register(PubSubLite, "run-pubsub-lite")

    module.run()
