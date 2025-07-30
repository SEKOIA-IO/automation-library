from ..base import BitdefenderAction

class UpdateCommentIncidentAction(BitdefenderAction):
    endpoint_api = "api/v1.0/jsonrpc/incidents"
    method_name = "updateIncidentNote"

    def run(self, arguments: dict) -> dict:
        if arguments.get("type") != "extendedIncidents" or arguments.get("type") != "incidents":
            raise ValueError("Invalid type provided. Must be 'extendedIncidents' or 'incidents'.")
        
        response = super().run(arguments)

        return {"result": response.get("result", False)}