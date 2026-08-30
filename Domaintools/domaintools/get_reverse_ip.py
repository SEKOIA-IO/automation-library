from sekoia_automation.action import Action
from .models import BaseDomaintoolsAction


class DomaintoolsReverseIP(BaseDomaintoolsAction, Action):
    action_name = "reverse_ip"
