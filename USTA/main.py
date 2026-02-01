from usta_modules.models import UstaModule

from usta_modules.usta_atp_connector import UstaAtpConnector


if __name__ == "__main__":
    module = UstaModule()
    module.register(UstaAtpConnector, "UstaAtpConnector")
    module.run()
