from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class RevokeUserSessionsArguments(NetskopeActionArguments):
    user_name: str = Field(..., description="The user name or email whose sessions should be revoked")


class RevokeUserSessionsAction(NetskopeAction):
    """
    Revoke active Netskope sessions and tokens for a user.
    """

    def run(self, arguments: dict) -> None:
        args = RevokeUserSessionsArguments(**arguments)
        self.initialize_action_arguments(args)

        self.execute_request("POST", "api/v2/events/token/revoke", json={"userName": args.user_name})

        self.log(
            level="info",
            message=f'Successfully revoked active Netskope sessions for "{args.user_name}"',
        )
