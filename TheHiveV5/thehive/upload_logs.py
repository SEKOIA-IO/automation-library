from typing import Any, Optional

from sekoia_automation.action import Action
from thehive4py.types.observable import OutputObservable

 # Upload logs <-> Add an observable as a log file OR add_attachment in alert
 ## See: https://docs.strangebee.com/thehive/api-docs/#tag/Observable/operation/Create%20Observable%20in%20Alert

from .thehiveconnector import TheHiveConnector

class TheHiveUploadLogsV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[OutputObservable]:

        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        arg_alert_id = arguments["alert_id"]
        arg_filepath = self._data_path.joinpath(arguments["filepath"])

        # Debug: log the constructed path
        print(f"DEBUG: _data_path = {self._data_path}")
        print(f"DEBUG: filepath argument = {arguments['filepath']}")
        print(f"DEBUG: Full constructed path = {arg_filepath}")
        print(f"DEBUG: File exists? {arg_filepath.exists()}")

        # Verify file exists before attempting upload
        if not arg_filepath.exists():
            error_msg = f"File not found: {arg_filepath}"
            print(f"ERROR: {error_msg}")
            raise FileNotFoundError(error_msg)

        try:
            # Convert Path to string for thehive4py compatibility
            result = api.alert_add_attachment(arg_alert_id, [str(arg_filepath)])
            print("Attachment uploaded:", result)
            return result
        except Exception as e:
            print("Error:", e)
            raise

        return None
