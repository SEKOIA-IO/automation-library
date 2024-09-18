from onepassword_modules import OnePasswordModule
from onepassword_modules.connector_1password_epm import OnePasswordConnector

if __name__ == "__main__":
    module = OnePasswordModule()
    module.register(OnePasswordConnector, "get_1password_epm_events")
    module.run()
