from stormshieldSNS.actions_base import StormshieldSNSAction
from stormshieldSNS.models.action_models import BlockIPAddressArguments


class BlockIPAddressAction(StormshieldSNSAction):
    name = "Block IP address"
    description = "Block an IP address on Stormshield SNS"

    def run(self, arguments: BlockIPAddressArguments) -> dict:
        self.log(f"Blocking IP address {arguments.ip_address} for {arguments.duration_s}s", level="info")
        result = self.client.block_ip(
            ip=arguments.ip_address,
            duration_s=arguments.duration_s,
        )
        self.log(f"IP address {arguments.ip_address} blocked successfully", level="info")
        return result
