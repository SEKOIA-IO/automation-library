from easyvista_modules.action_base import EasyVistaAction
from easyvista_modules.helpers import select_fields
from easyvista_modules.models import ViewRequestIncidentCommentArguments


class ViewRequestIncidentComment(EasyVistaAction):
    def run(self, arguments: dict) -> dict | None:
        args = ViewRequestIncidentCommentArguments(**arguments)
        return select_fields(
            self.get(self.request_path(args.rfc_number, "comment")),
            {"href": "HREF", "parent_href": "PARENT_HREF", "comment": "COMMENT"},
        )
