from sekoia_automation.action import Action
from .models import BaseDomaintoolsAction


class DomaintoolsReverseDomain(BaseDomaintoolsAction, Action):
    action_name = "reverse_domain"
