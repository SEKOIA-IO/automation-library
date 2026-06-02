try:
    from actions.comment_attempt import (
        CommentAttemptAction,
        CommentAttemptArguments,
    )
    from actions.request_credential_check import (
        RequestCredentialCheckAction,
        RequestCredentialCheckArguments,
    )
except ModuleNotFoundError:
    from .comment_attempt import (
        CommentAttemptAction,
        CommentAttemptArguments,
    )
    from .request_credential_check import (
        RequestCredentialCheckAction,
        RequestCredentialCheckArguments,
    )

__all__ = [
    "CommentAttemptAction",
    "CommentAttemptArguments",
    "RequestCredentialCheckAction",
    "RequestCredentialCheckArguments",
]
