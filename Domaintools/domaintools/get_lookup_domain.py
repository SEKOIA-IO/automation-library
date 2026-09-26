from sekoia_automation.action import Action
from .models import BaseDomaintoolsAction


class DomaintoolsLookupDomain(BaseDomaintoolsAction, Action):
    action_name = "lookup_domain"
