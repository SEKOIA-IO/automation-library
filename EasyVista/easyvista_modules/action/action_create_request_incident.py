from urllib.parse import unquote, urlsplit

from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import map_fields
from easyvista_modules.models import CreateRequestIncidentArguments


class CreateRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = CreateRequestIncidentArguments(**arguments)
        mapping = {
            "catalog_code": "Catalog_Code",
            "title": "TITLE",
            "description": "Description",
            "urgency_id": "Urgency_ID",
            "impact_id": "IMPACT_ID",
            "recipient_name": "Recipient_Name",
            "recipient_mail": "Recipient_Mail",
            "department_code": "Department_Code",
            "location_id": "Location_ID",
        }
        result = self.request_href(
            "POST", "/requests", json={"requests": [map_fields(item, mapping) for item in args.requests]}
        )
        if result and result.get("href"):
            result["rfc_number"] = unquote(urlsplit(result["href"]).path.rstrip("/").rsplit("/", 1)[-1])
        return result
