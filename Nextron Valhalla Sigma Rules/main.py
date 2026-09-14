from nextron_valhalla_sigma_rules_modules import (
    NextronValhallaSigmaRulesModule,
    SyncSigmaRulesCatalog,
)

if __name__ == "__main__":
    module = NextronValhallaSigmaRulesModule()
    module.register(SyncSigmaRulesCatalog, "sync-sigma-rules-catalog")
    module.run()
