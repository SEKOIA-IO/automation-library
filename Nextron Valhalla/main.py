from nextron_valhalla_modules import (
    NextronValhallaModule,
    SyncSigmaRulesCatalog,
)

if __name__ == "__main__":
    module = NextronValhallaModule()
    module.register(SyncSigmaRulesCatalog, "sync-sigma-rules-catalog")
    module.run()
