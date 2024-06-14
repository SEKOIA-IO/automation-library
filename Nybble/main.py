from nybble_modules import NybbleModule

from nybble_modules.create_alert import CreateAlertAction


if __name__ == "__main__":
    module = NybbleModule()
    module.register(CreateAlertAction, "CreateAlertAction")
    module.run()
