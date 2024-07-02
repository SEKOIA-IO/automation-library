from sekoia_automation.module import Module

from google_module.big_query import BigQueryAction
from google_module.pubsub import PubSub
from google_module.google_reports import GoogleReports

if __name__ == "__main__":
    module = Module()

    module.register(BigQueryAction, "run-bigquery-query")
    module.register(PubSub, "run-pubsub")
    module.register(GoogleReports, "run-google_reports_trigger")
    module.register(GoogleReports, "run-login_reports_trigger")

    module.run()
