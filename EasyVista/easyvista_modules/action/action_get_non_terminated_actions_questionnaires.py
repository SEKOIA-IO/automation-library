from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import QUESTIONNAIRE_FIELDS, select_fields
from easyvista_modules.models import GetNonTerminatedActionsQuestionnairesArguments


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
