from extrahop import ExtraHopModule
from extrahop.reveal_360_trigger import ExtraHopReveal360Connector

if __name__ == "__main__":
    module = ExtraHopModule()
    module.register(ExtraHopReveal360Connector, "extrahop_reveal_360")
    module.run()
