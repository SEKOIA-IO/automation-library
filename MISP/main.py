from misp.misp_to_stix import MISPToSTIXAction
from misp.publish_to_misp import PublishToMISPAction
from misp.trigger import MISPTrigger
from sekoia_automation.module import Module
from misp.trigger_misp_ids_attributes_to_ioc_collection import MISPIDSAttributesToIOCCollectionTrigger

if __name__ == "__main__":
    module = Module()

    module.register(MISPTrigger, "trigger")
    module.register(MISPToSTIXAction, "convert-misp-to-stix")
    module.register(PublishToMISPAction, "publish-to-misp")

    # Register new trigger
    module.register(MISPIDSAttributesToIOCCollectionTrigger, "trigger-misp-ids-to-ioc-collection")

    module.run()