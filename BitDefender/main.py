from sekoia_automation.module import Module

from bitdefender.actions import IsolateEndpointAction, DeisolateEndpointAction

if __name__ == "__main__":
    module = Module()
    module.register(IsolateEndpointAction, "bitdefender_gravity_zone_isolate_endpoint")
    module.register(DeisolateEndpointAction, "bitdefender_gravity_zone_deisolate_endpoint")
    module.run()