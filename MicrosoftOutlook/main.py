from microsoft_outlook_modules import MicrosoftOutlookModule
from microsoft_outlook_modules.action_delete_message import DeleteMessageAction
from microsoft_outlook_modules.action_forward_message import ForwardMessageAction
from microsoft_outlook_modules.action_get_message import GetMessageAction
from microsoft_outlook_modules.action_update_message import UpdateMessageAction

if __name__ == "__main__":
    module = MicrosoftOutlookModule()
    module.register(ForwardMessageAction, "action_forward_message")
    module.register(GetMessageAction, "action_get_message")
    module.register(DeleteMessageAction, "action_delete_message")
    module.register(UpdateMessageAction, "action_update_message")
    module.run()
