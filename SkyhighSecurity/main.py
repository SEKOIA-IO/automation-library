from sekoia_automation.module import Module

from gateway_cloud_services.trigger_skyhigh_security_swg import SkyhighSecuritySWGTrigger

if __name__ == "__main__":
    module = Module()
    module.register(SkyhighSecuritySWGTrigger, "skyhigh_security_swg")
    module.run()
