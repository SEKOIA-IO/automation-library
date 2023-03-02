from sekoia_automation.module import Module

from okta_modules.models import OktaModuleConfiguration


class OktaModule(Module):
    configuration: OktaModuleConfiguration
