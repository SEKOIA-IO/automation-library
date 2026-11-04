from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import QUESTIONNAIRE_FIELDS, select_fields
from easyvista_modules.models import GetSpecificActionQuestionnaireArguments


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
