from easyvista.action_base import EasyVistaAction, json_body
from easyvista.actions_requests import href_result, map_fields
from easyvista.models import CreateRelatedActionIncidentArguments, CreateTaskRequestIncidentArguments


def validate_identifiers(action: EasyVistaAction, values: dict, type_fields: tuple[str, ...]) -> bool:
    if not any(values.get(name) for name in type_fields):
        action.error("Provide one of " + (", ".join(type_fields[:-1]) + " or " + type_fields[-1]))
        return False
    if not any(values.get(name) for name in ("group_id", "group_name", "group_mail")):
        action.error("Provide one of group_id, group_name or group_mail")
        return False
    return True


class CreateRelatedActionIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = CreateRelatedActionIncidentArguments(**arguments)
        body = args.action.model_dump(exclude_none=True)
        if not validate_identifiers(self, body, ("action_type_id", "action_type_name", "action_type_guid")):
            return None
        response = self.request("POST", self.request_path(args.rfc_number, "actions"), json={"action": body})
        if response is None:
            return None
        return {"success": True, "status_code": response.status_code, **(href_result(json_body(response)) or {})}


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
        return href_result(json_body(response)) or {}
