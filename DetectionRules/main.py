from sekoia_automation.module import Module

from detection_rules.trigger_snort_rules import SnortRulesTrigger

if __name__ == "__main__":
    module = Module()

    module.register(SnortRulesTrigger, "snort_rules_trigger")

    module.run()
