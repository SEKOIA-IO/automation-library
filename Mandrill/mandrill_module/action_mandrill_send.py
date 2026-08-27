import mailchimp_transactional as mailchimp_transactional
from mailchimp_transactional.api_client import ApiClientError
from sekoia_automation.action import Action


class MandrillSendAction(Action):
    """
    Action to send an email
    """

    def run(self, arguments) -> dict | None:
        client = mailchimp_transactional.Client(self.module.configuration.get("apikey"))

        message = {
            "message": arguments["message"],
            "ip_pool": arguments.get("ip_pool"),
            "send_at": arguments.get("send_at"),
        }

        try:
            return {"report": client.messages.send(message)}
        except ApiClientError as exp:
            self.error(str(exp.text))

        return None
