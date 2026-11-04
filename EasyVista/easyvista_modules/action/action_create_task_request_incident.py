from easyvista_modules.action_base import EasyVistaAction, json_body
from easyvista_modules.helpers import map_fields, validate_identifiers
from easyvista_modules.models import CreateTaskRequestIncidentArguments


class CreateTaskRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = CreateTaskRequestIncidentArguments(**arguments)
        body = map_fields(
            args,
            {
                "action_type_id": "action_type_id",
                "action_type_name": "action_type_name",
                "group_id": "group_id",
                "group_name": "group_name",
                "group_mail": "group_mail",
                "description": "description",
                "elapsed_time": "Elapsed_Time",
                "time_cost": "time_cost",
                "contractual_cost": "contractual_cost",
                "creation_date_ut": "creation_date_ut",
                "start_date_ut": "start_date_ut",
                "end_date_ut": "end_date_ut",
            },
        )
        if not validate_identifiers(self, body, ("action_type_id", "action_type_name")):
            return None
        response = self.request("POST", self.request_path(args.rfc_number, "tasks"), json=body)
        if response is None:
            return None
        return self.href_result(json_body(response))
