# third parties
from sekoia_automation.module import Module

from mattermost.action_mattermost_postalert import MattermostPostAlertAction

# internals
from mattermost.action_mattermost_postmessage import MattermostPostMessageAction

if __name__ == "__main__":
    module = Module()
    module.register(MattermostPostMessageAction, "mattermost_post_message")
    module.register(MattermostPostAlertAction, "mattermost_post_alert")
    module.run()
