from sekoia_automation.module import Module

from google_module.account_validator import GoogleAccountValidator
from google_module.asset_connector.user_assets import GoogleWorkspaceUserAssetConnector
from google_module.big_query import BigQueryAction
from google_module.google_reports import GoogleReports
from google_module.pubsub import PubSub

if __name__ == "__main__":
    module = Module()
    module.register_account_validator(GoogleAccountValidator)

    module.register(BigQueryAction, "run-bigquery-query")
    module.register(PubSub, "run-pubsub")
    module.register(GoogleReports, "run-google_reports_trigger")
    module.register(GoogleReports, "run-login_reports_trigger")
    module.register(GoogleWorkspaceUserAssetConnector, "google_workspace_user_asset_connector")

    module.run()
