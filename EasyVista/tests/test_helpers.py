from easyvista_modules.helpers import map_fields
from easyvista_modules.models import CloseRequestIncidentArguments


def test_empty_text_filter_preserves_false():
    args = CloseRequestIncidentArguments(rfc_number="ticket", comment="", delete_actions=False)
    assert map_fields(args, {"comment": "COMMENT", "delete_actions": "DELETE_ACTIONS"}) == {"DELETE_ACTIONS": False}
