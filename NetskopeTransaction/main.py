from sekoia_automation.module import Module

from module.pubsub_lite import PubSubLite

if __name__ == "__main__":
    module = Module()
    module.register(PubSubLite, "run-pubsub-lite")

    module.run()
