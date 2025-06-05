from xsiam import XsiamModule
from xsiam.stix_to_xsiam import STIXToXSIAMAction

if __name__ == "__main__":
    module = XsiamModule()
    module.register(STIXToXSIAMAction, "stix_to_xsiam_action")
    module.run()
