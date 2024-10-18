from sekoia_automation.module import Module

from groupby.action_groupby import GroupProcessor


if __name__ == "__main__":
    module = Module()

    module.register(GroupProcessor, "action_groupby")

    module.run()
