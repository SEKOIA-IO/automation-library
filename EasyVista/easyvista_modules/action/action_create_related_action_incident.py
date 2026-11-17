from easyvista_modules.action_base import EasyVistaAction, json_body
from easyvista_modules.helpers import validate_identifiers
from easyvista_modules.models import CreateRelatedActionIncidentArguments


class CreateRelatedActionIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = CreateRelatedActionIncidentArguments(**arguments)
        body = args.action.model_dump(exclude_none=True)
        if not validate_identifiers(self, body, ("action_type_id", "action_type_name", "action_type_guid")):
            return None
        response = self.request("POST", self.request_path(args.rfc_number, "actions"), json={"action": body})
        if response is None:
            return None
        href = self.href_result(json_body(response), required=False)
        if href is None:
            return None
        return {"success": True, "status_code": response.status_code, **href}
