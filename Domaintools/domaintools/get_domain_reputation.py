from sekoia_automation.action import Action
from .models import BaseDomaintoolsAction


class DomaintoolsDomainReputation(BaseDomaintoolsAction, Action):
    action_name = "domain_reputation"
