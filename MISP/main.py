from misp.misp_to_stix import MISPToSTIXAction
from misp.publish_to_misp import PublishToMISPAction
from misp.trigger import MISPTrigger
from sekoia_automation.module import Module

if __name__ == "__main__":
    module = Module()

    module.register(MISPTrigger, "trigger")
    module.register(MISPToSTIXAction, "convert-misp-to-stix")
    module.register(PublishToMISPAction, "publish-to-misp")

    module.run()
