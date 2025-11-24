from new_relic_modules import NewRelicModule
from new_relic_modules.action_nrql_query import NRQLQueryAction

if __name__ == "__main__":
    module = NewRelicModule()
    module.register(NRQLQueryAction, "action_nrql_query")
    module.run()
