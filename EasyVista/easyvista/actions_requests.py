from urllib.parse import unquote, urlsplit

from pydantic import BaseModel

from easyvista.action_base import EasyVistaAction
from easyvista.models import (
    CloseRequestIncidentArguments,
    CreateRequestIncidentArguments,
    RestartRequestIncidentArguments,
    SuspendRequestIncidentArguments,
    UpdateRequestIncidentArguments,
)


def map_fields(model: BaseModel, mapping: dict[str, str]) -> dict:
    """Keep custom names verbatim; explicit fields win even with different casing."""
    values = model.model_dump(exclude_none=True)
    explicit = {api_name: values[name] for name, api_name in mapping.items() if name in values}
    explicit_names = {name.casefold() for name in explicit}
    custom = {
        key: value
        for key, value in (values.get("custom_fields") or {}).items()
        if key.casefold() not in explicit_names and value is not None
    }
    return {**custom, **explicit}


def href_result(data: dict | None) -> dict | None:
    if data is None:
        return None
    return {"href": data["HREF"]} if "HREF" in data else {}


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
        data = self.post("/requests", json={"requests": [map_fields(item, mapping) for item in args.requests]})
        result = href_result(data)
        if result and result.get("href"):
            result["rfc_number"] = unquote(urlsplit(result["href"]).path.rstrip("/").rsplit("/", 1)[-1])
        return result


class UpdateRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = UpdateRequestIncidentArguments(**arguments)
        body = map_fields(
            args,
            {
                "description": "Description",
                "urgency_id": "Urgency_ID",
                "external_reference": "External_reference",
                "asset": "ASSET",
                "asset_serial": "ASSET_SERIAL",
                "ci": "CI",
                "ci_id": "CI_ID",
            },
        )
        if not body:
            self.error("Nothing to update: provide at least one field")
            return None
        if not self.ensure_open(args.rfc_number):
            return None
        params = {"append": str(args.append).lower()} if args.append is not None else {}
        return href_result(self.put(self.request_path(args.rfc_number), json=body, params=params))


class CloseRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = CloseRequestIncidentArguments(**arguments)
        if not self.ensure_open(args.rfc_number):
            return None
        body = map_fields(
            args,
            {
                "status_guid": "STATUS_GUID",
                "comment": "COMMENT",
                "end_date": "END_DATE",
                "catalog_guid": "CATALOG_GUID",
                "delete_actions": "DELETE_ACTIONS",
            },
        )
        if args.delete_actions is not None:
            body["DELETE_ACTIONS"] = int(args.delete_actions)
        return href_result(self.put(self.request_path(args.rfc_number, "close"), json=body))


class SuspendRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = SuspendRequestIncidentArguments(**arguments)
        body = map_fields(args, {"comment": "comment", "done_by_id": "done_by_id"})
        return href_result(self.put(self.request_path(args.rfc_number, "suspend"), json=body))


class RestartRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = RestartRequestIncidentArguments(**arguments)
        body = map_fields(args, {"comment": "Comment", "done_by_id": "done_by_id"})
        return href_result(self.put(self.request_path(args.rfc_number, "restart"), json=body))
