from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class RestrictUserToGroupArguments(NetskopeActionArguments):
    user_name: str = Field(..., description="The user name or email to restrict")
    group_ids: list[str] = Field(
        ..., description="The restrictive Netskope group identifiers"
    )


class RestrictUserToGroupAction(NetskopeAction):
    """
    Assign a Netskope user to a restricted SCIM group.
    """

    def run(self, arguments: dict) -> None:
        args = RestrictUserToGroupArguments(**arguments)
        self.initialize_action_arguments(args)

        search_result = self.execute_request(
            "GET",
            "api/v2/scim/Users",
            params={"filter": f'userName eq "{args.user_name}"'},
        )
        users = search_result.get("Resources", []) or search_result.get("resources", [])
        if not users:
            raise ValueError(
                f'Unable to find Netskope user for userName "{args.user_name}"'
            )

        user = users[0]
        user_id = user.get("id") or user.get("uuid")
        if not user_id:
            raise ValueError(
                f'Unable to find Netskope user identifier for userName "{args.user_name}"'
            )

        self.execute_request(
            "PATCH",
            f"api/v2/scim/Users/{user_id}",
            json={"groups": [{"value": group_id} for group_id in args.group_ids]},
        )

        self.log(
            level="info",
            message=(
                f'Successfully restricted Netskope user "{args.user_name}" '
                f"(id = {user_id}) to {len(args.group_ids)} group(s)"
            ),
        )
