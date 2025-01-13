from eset_modules import EsetModule
from eset_modules.action_deisolate_endpoint import EsetDeIsolateEndpointAction
from eset_modules.action_isolate_endpoint import EsetIsolateEndpointAction
from eset_modules.action_scan import EsetScanAction

if __name__ == "__main__":
    module = EsetModule()
    module.register(EsetScanAction, "EsetScanAction")
    module.register(EsetIsolateEndpointAction, "EsetIsolateEndpointAction")
    module.register(EsetDeIsolateEndpointAction, "EsetDeIsolateEndpointAction")
    module.run()
