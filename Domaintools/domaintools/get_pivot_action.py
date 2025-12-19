from sekoia_automation.action import Action
from .models import BaseDomaintoolsAction


class DomaintoolsPivotAction(BaseDomaintoolsAction, Action):
    action_name = "pivot_action"
