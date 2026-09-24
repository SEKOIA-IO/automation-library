from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class DeployUrlPolicyArguments(NetskopeActionArguments):
    pass


class DeployUrlPolicyAction(NetskopeAction):
    """
    Deploy pending Netskope URL policy changes.
    """

    def run(self, arguments: dict) -> None:
        args = DeployUrlPolicyArguments(**arguments)
        self.initialize_action_arguments(args)

        self.deploy_blocklist_changes()

        self.log(level="info", message="Successfully deployed pending URL policy changes")
