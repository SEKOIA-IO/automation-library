import base64
import binascii

from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.models import UploadAttachDocumentRequestIncidentArguments


class UploadAttachDocumentRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = UploadAttachDocumentRequestIncidentArguments(**arguments)
        try:
            for document in args.documents:
                base64.b64decode(document.filedata, validate=True)
        except ValueError, binascii.Error:
            self.error("documents[*].filedata is not valid base64")
            return None
        body: dict = {"documents": [item.model_dump() for item in args.documents]}
        if args.description:
            body["description"] = args.description
        return self.request_href("POST", self.request_path(args.rfc_number, "documents"), json=body)
