from sekoia_automation.module import Module

from zscaler.block_ioc import ZscalerBlockIOC

if __name__ == "__main__":
    module = Module()
    module.register(ZscalerBlockIOC, "zscaler_block_ioc")

    module.run()
