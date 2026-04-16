from sekoia_automation.module import Module

from stormshieldSNS.block_ip_action import BlockIPAddressAction

if __name__ == "__main__":
    module = Module()
    module.register(BlockIPAddressAction, "stormshield_sns_block_ip")
    module.run()
