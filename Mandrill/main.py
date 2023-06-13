from sekoia_automation.module import Module

from mandrill_module.action_mandrill_send import MandrillSendAction

if __name__ == "__main__":
    module = Module()

    module.register(MandrillSendAction, "mandrill_send")

    module.run()
