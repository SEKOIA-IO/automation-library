from sekoia_automation.module import Module

from zscaler.actions import ZscalerActivateChanges, ZscalerBlockIOC, ZscalerPushIOCBlock, ZscalerUnBlockIOC

if __name__ == "__main__":
    module = Module()
    module.register(ZscalerBlockIOC, "zscaler_block_ioc")
    module.register(ZscalerPushIOCBlock, "zscaler_push_iocs_block")
    module.register(ZscalerUnBlockIOC, "zscaler_unblock_ioc")
    module.register(ZscalerActivateChanges, "zscaler_activate_changes")

    module.run()
