from vectra_modules import VectraModule
from vectra_modules.connector_vectra_entity_scoring import VectraEntityScoringConnector

if __name__ == "__main__":
    module = VectraModule()
    module.register(VectraEntityScoringConnector, "vectra_entity_scoring")
    module.run()
