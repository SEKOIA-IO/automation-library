import enum

from pydantic import BaseModel


class HostAction(enum.Enum):
    """Mapping of available device actions based on docs."""

    lift_containment = "lift_containment"
    contain = "contain"
    hide_host = "hide_host"
    unhide_host = "unhide_host"


class AlertAction(enum.Enum):
    add_tag = "add_tag"
    append_comment = "append_comment"
    assign_to_name = "assign_to_name"
    assign_to_user_id = "assign_to_user_id"
    assign_to_uuid = "assign_to_uuid"
    remove_tag = "remove_tag"
    remove_tags_by_prefix = "remove_tags_by_prefix"
    show_in_ui = "show_in_ui"
    unassign = "unassign"
    update_status = "update_status"


class UpdateAlertParameter(BaseModel):
    name: AlertAction
    value: str

    class Config:
        use_enum_values = True
