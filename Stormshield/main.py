
from stormshieldSNS.block_ip_action import BlockIPAddressAction
from stormshieldSNS.models.common_models import StormshieldSNSModule

if __name__ == "__main__":
    module = StormshieldSNSModule()
    module.register(BlockIPAddressAction, "stormshield_sns_block_ip")
    module.run()
