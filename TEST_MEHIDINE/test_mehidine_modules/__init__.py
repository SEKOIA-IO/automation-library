from sekoia_automation.module import Module
from test_mehidine_modules.models import Test_MehidineModuleConfiguration


class Test_MehidineModule(Module):
    configuration: Test_MehidineModuleConfiguration
