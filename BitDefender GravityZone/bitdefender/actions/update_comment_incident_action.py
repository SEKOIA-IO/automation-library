from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_update_incident_note


class UpdateCommentIncidentAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        if arguments.get("type") not in {"extendedIncidents", "incidents"}:
            raise ValueError("Invalid type provided. Must be 'extendedIncidents' or 'incidents'.")

        response = self.execute_request(prepare_update_incident_note(arguments))
        return {"result": response.get("result", False)}
