from easyvista.action_base import EasyVistaAction
from easyvista.models import (
    GetNonTerminatedActionsQuestionnairesArguments,
    GetSpecificActionQuestionnaireArguments,
    ViewRequestIncidentArguments,
    ViewRequestIncidentCommentArguments,
    ViewRequestIncidentProblemArguments,
    ViewRequestsIncidentsListArguments,
)


def select_fields(data: dict | None, mapping: dict[str, str]) -> dict | None:
    if data is None:
        return None
    return {name: data[api_name] for name, api_name in mapping.items() if api_name in data}


LIST_FIELDS = {
    "href": "HREF",
    "record_count": "record_count",
    "total_record_count": "total_record_count",
    "records": "records",
}
QUESTIONNAIRE_FIELDS = {
    "href": "HREF",
    "record_count": "record_count",
    "total_record_count": "total_record_count",
    "results": "results",
}


class ViewRequestsIncidentsList(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestsIncidentsListArguments(**arguments)
        return select_fields(self.get("/requests", params=args.model_dump(exclude_none=True)), LIST_FIELDS)


class ViewRequestIncident(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestIncidentArguments(**arguments)
        data = self.get(self.request_path(args.rfc_number))
        if data is None:
            return None
        return {**(select_fields(data, {"href": "HREF"}) or {}), "record": data}


class ViewRequestIncidentProblem(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestIncidentProblemArguments(**arguments)
        return select_fields(self.get(self.request_path(args.rfc_number, "problem")), LIST_FIELDS)


class ViewRequestIncidentComment(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestIncidentCommentArguments(**arguments)
        return select_fields(
            self.get(self.request_path(args.rfc_number, "comment")),
            {"href": "HREF", "parent_href": "PARENT_HREF", "comment": "COMMENT"},
        )


class GetNonTerminatedActionsQuestionnaires(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = GetNonTerminatedActionsQuestionnairesArguments(**arguments)
        return select_fields(
            self.get(
                self.request_path(args.current_incident, "actions", "questionnaire"),
                params={"actionTypeId": args.action_type_id},
            ),
            QUESTIONNAIRE_FIELDS,
        )


class GetSpecificActionQuestionnaire(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = GetSpecificActionQuestionnaireArguments(**arguments)
        return select_fields(
            self.get(
                self.request_path(args.current_incident, "actions", args.action_id, "questionnaire"),
                params={"actionTypeId": args.action_type_id},
            ),
            QUESTIONNAIRE_FIELDS,
        )
