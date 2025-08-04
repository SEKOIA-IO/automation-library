from ..base import BitdefenderAction
from ..bitdefender_gravity_zone_api import prepare_update_incident_note_endpoint
class UpdateCommentIncidentAction(BitdefenderAction):

    def run(self, arguments: dict) -> dict:
        if arguments.get("type") != "extendedIncidents" and arguments.get("type") != "incidents":
            raise ValueError("Invalid type provided. Must be 'extendedIncidents' or 'incidents'.")
        
        response = self.execute_request(
            prepare_update_incident_note_endpoint(arguments)
        )
        return {"result": response.get("result", False)}