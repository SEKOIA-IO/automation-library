from lacework_module.base import LaceworkModule
from lacework_module.lacework_connector import LaceworkEventsTrigger

if __name__ == "__main__":
    module = LaceworkModule()
    module.register(LaceworkEventsTrigger, "lacework_query_alerts")
    module.run()
