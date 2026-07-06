from actions.comment_attempt import CommentAttemptAction
from actions.request_credential_check import RequestCredentialCheckAction
from connectors.attempts import MoknLoginAttemptsTrigger
from module import MoknModule

if __name__ == "__main__":
    module = MoknModule()
    module.register(CommentAttemptAction, "comment_attempt")
    module.register(MoknLoginAttemptsTrigger, "mokn_login_attempts_trigger")
    module.register(RequestCredentialCheckAction, "request_credential_check")
    module.run()
