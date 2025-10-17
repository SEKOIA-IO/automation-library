from sekoia_automation.module import Module

from thehive.create_alert import TheHiveCreateAlertV5
from thehive.add_commment import TheHiveCreateCommentV5
from thehive.add_observable import TheHiveCreateObservableV5
from thehive.upload_logs import TheHiveUploadLogsV5

if __name__ == "__main__":
    module = Module()

    module.register(TheHiveCreateAlertV5, "thehive_create_alert")
    module.register(TheHiveCreateCommentV5, "thehive_add_comment")
    module.register(TheHiveCreateObservableV5, "thehive_add_observable")
    module.register(TheHiveUploadLogsV5, "thehive_upload_logs")

    module.run()
