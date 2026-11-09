import base64

from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.models import GetRequestIncidentDocumentArguments


class GetRequestIncidentDocument(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = GetRequestIncidentDocumentArguments(**arguments)
        response = self.request("GET", self.request_path(args.rfc_number, "documents", args.id), file_response=True)
        if response is None:
            return None
        return {
            "content_type": response.headers.get("Content-Type", "application/octet-stream"),
            "content_base64": base64.b64encode(response.content).decode("ascii"),
        }
