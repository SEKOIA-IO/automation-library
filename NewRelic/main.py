from new_relic_modules import NewRelicModule
from new_relic_modules.action_nrql_query import NRQLQueryAction


def main():
    module = NewRelicModule()
    module.register(NRQLQueryAction, "action_nrql_query")
    module.run()


def fission_main():
    main()
    return "ok"


if __name__ == "__main__":
    main()
