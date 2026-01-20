from typing import Any
from sekoia_automation.action import Action

# Upload logs <-> Add an observable as a log file OR add_attachment in alert
## See: https://docs.strangebee.com/thehive/api-docs/#tag/Observable/operation/Create%20Observable%20in%20Alert

from .thehiveconnector import TheHiveConnector
from .helpers import copy_to_tempfile


class TheHiveUploadLogsV5(Action):
    def run(self, arguments: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
            verify=self.module.configuration.get("verify_certificate", True),
        )

        arg_alert_id = arguments["alert_id"]
        arg_filepath = self.data_path.joinpath(arguments["filepath"])

        # Verify file exists before attempting upload
        if not arg_filepath.exists():
            error_msg = f"File not found: {arg_filepath}"
            raise FileNotFoundError(error_msg)

        # copy locally the file as TheHive API requires a physical file (not one in the remote storage)
        file_name: str
        with copy_to_tempfile(arg_filepath) as file_name:
            return {"outputAttachment": api.alert_add_attachment(arg_alert_id, [file_name])}
