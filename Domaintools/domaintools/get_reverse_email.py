from sekoia_automation.action import Action
from .models import BaseDomaintoolsAction


class DomaintoolsReverseEmail(BaseDomaintoolsAction, Action):
    action_name = "reverse_email"
