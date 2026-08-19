from brevohttp_modules import BrevoHttpModule

from brevohttp_modules.connector import BrevoConnector

if __name__ == "__main__":
    module = BrevoHttpModule()
    module.register(BrevoConnector, "BrevoConnector")
    module.run()
