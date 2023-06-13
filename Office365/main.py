from sekoia_automation.module import Module

from office365.message_trace.trigger_office365_messagetrace import (
    Office365MessageTraceTrigger,
)
from office365.message_trace.trigger_office365_messagetrace_oauth import (
    Office365MessageTraceTrigger as Office365MessageTraceTrigger_oauth,
)

if __name__ == "__main__":
    module = Module()
    module.register(Office365MessageTraceTrigger, "office365_messagetrace_trigger")
    module.register(Office365MessageTraceTrigger_oauth, "office365_messagetrace_trigger_oauth")
    module.run()
