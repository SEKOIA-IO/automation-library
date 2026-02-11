from ldap3.core.exceptions import LDAPException

from microsoft_ad.actions_base import MicrosoftADAction
from microsoft_ad.models.action_models import ResetPassUserArguments, UserAccountArguments

# 512 is the default value for userAccountControl for enabled accounts
DEFAULT_UAC = 512


class ResetUserPasswordAction(MicrosoftADAction):
    name = "Reset Password"
    description = "Reset password with an rdp connection with an admin account"

    def _reset_password_for_user(self, user_dn: str, username: str, new_password: str) -> None:
        try:
            self.client.extend.microsoft.modify_password(user_dn, new_password)
        except LDAPException as e:
            raise Exception(f"Failed to reset password for account {username}: {e}") from e

        if self.client.result.get("description") != "success":
            raise Exception(f"Password reset failed for {username}: {self.client.result.get('description')}")

    def run(self, arguments: ResetPassUserArguments):
        self.log(f"Starting password reset for user: {arguments.username}", level="info")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn, arguments.display_name)

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1 and not arguments.apply_to_all:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        if len(user_query) == 1 and not arguments.apply_to_all:
            user_dn = user_query[0][0]
            self._reset_password_for_user(user_dn, arguments.username, arguments.new_password)
            self.log(f"Password reset successful for user: {arguments.username}", level="info")
            return None

        results: list[dict] = []
        for user_dn, _ in user_query:
            try:
                self._reset_password_for_user(user_dn, arguments.username, arguments.new_password)
                results.append({"dn": user_dn, "status": "success"})
                self.log(f"Password reset successful for user: {user_dn}", level="info")
            except Exception as e:
                results.append({"dn": user_dn, "status": "failed", "error": str(e)})
                self.log(f"Password reset failed for user {user_dn}: {e}", level="error")

        total_success = sum(1 for r in results if r["status"] == "success")
        total_failed = sum(1 for r in results if r["status"] == "failed")

        if total_success == 0:
            raise Exception(f"All password resets failed for {arguments.username}")

        return {
            "affected_users": results,
            "total_found": len(user_query),
            "total_success": total_success,
            "total_failed": total_failed,
        }


class EnableUserAction(MicrosoftADAction):
    name = "Enable User"
    description = "Enable an Azure Active Directory user"

    def _enable_user(self, user_dn: str, current_uac: int | None, username: str) -> None:
        uac_disabled = 2
        uac = current_uac if current_uac is not None else DEFAULT_UAC
        new_uac = uac & ~uac_disabled

        try:
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", new_uac)]}, None)
        except LDAPException as e:
            raise Exception(f"Failed to enable {username} account: {e}") from e

        if self.client.result.get("description") != "success":
            raise Exception(f"Enable action failed for {username}: {self.client.result.get('description')}")

    def run(self, arguments: UserAccountArguments):
        self.log(f"Starting enabling user account: {arguments.username}", level="info")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn, arguments.display_name)

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1 and not arguments.apply_to_all:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        if len(user_query) == 1 and not arguments.apply_to_all:
            user_dn = user_query[0][0]
            current_uac = user_query[0][1]
            self.log(f"User DN: {user_dn} and userAccountControl value {current_uac} were found", level="info")
            self._enable_user(user_dn, current_uac, arguments.username)
            self.log(f"User {arguments.username} enabled successfully", level="info")
            return None

        results: list[dict] = []
        for user_dn, current_uac in user_query:
            try:
                self._enable_user(user_dn, current_uac, arguments.username)
                results.append({"dn": user_dn, "status": "success"})
                self.log(f"User {user_dn} enabled successfully", level="info")
            except Exception as e:
                results.append({"dn": user_dn, "status": "failed", "error": str(e)})
                self.log(f"Failed to enable user {user_dn}: {e}", level="error")

        total_success = sum(1 for r in results if r["status"] == "success")
        total_failed = sum(1 for r in results if r["status"] == "failed")

        if total_success == 0:
            raise Exception(f"All enable operations failed for {arguments.username}")

        return {
            "affected_users": results,
            "total_found": len(user_query),
            "total_success": total_success,
            "total_failed": total_failed,
        }


class DisableUserAction(MicrosoftADAction):
    name = "Disable User"
    description = "Disable an Azure Active Directory user"

    def _disable_user(self, user_dn: str, current_uac: int | None, username: str) -> None:
        uac_disabled = 2
        uac = current_uac if current_uac is not None else DEFAULT_UAC
        new_uac = uac | uac_disabled

        try:
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", new_uac)]}, None)
        except LDAPException as e:
            raise Exception(f"Failed to disable {username} account: {e}") from e

        if self.client.result.get("description") != "success":
            raise Exception(f"Disable action failed for {username}: {self.client.result.get('description')}")

    def run(self, arguments: UserAccountArguments):
        self.log(f"Starting disable action for user: {arguments.username}", level="info")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn, arguments.display_name)

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1 and not arguments.apply_to_all:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        if len(user_query) == 1 and not arguments.apply_to_all:
            user_dn = user_query[0][0]
            current_uac = user_query[0][1]
            self.log(f"User DN: {user_dn} and userAccountControl value {current_uac} were found", level="info")
            self._disable_user(user_dn, current_uac, arguments.username)
            self.log(f"User {arguments.username} has been disabled successfully", level="info")
            return None

        results: list[dict] = []
        for user_dn, current_uac in user_query:
            try:
                self._disable_user(user_dn, current_uac, arguments.username)
                results.append({"dn": user_dn, "status": "success"})
                self.log(f"User {user_dn} has been disabled successfully", level="info")
            except Exception as e:
                results.append({"dn": user_dn, "status": "failed", "error": str(e)})
                self.log(f"Failed to disable user {user_dn}: {e}", level="error")

        total_success = sum(1 for r in results if r["status"] == "success")
        total_failed = sum(1 for r in results if r["status"] == "failed")

        if total_success == 0:
            raise Exception(f"All disable operations failed for {arguments.username}")

        return {
            "affected_users": results,
            "total_found": len(user_query),
            "total_success": total_success,
            "total_failed": total_failed,
        }
