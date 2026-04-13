from ldap3.core.exceptions import LDAPException

from microsoft_ad.actions_base import MicrosoftADAction
from microsoft_ad.models.action_models import (
    ResetPassUserArguments,
    UserAccountArguments,
)

# 512 is the default value for userAccountControl for enabled accounts
DEFAULT_UAC = 512


class ResetUserPasswordAction(MicrosoftADAction):
    name = "Reset Password"
    description = "Reset password with an rdp connection with an admin account"

    def _reset_password_for_user(self, user_dn: str, username: str | None, new_password: str | None) -> None:
        self.log(
            f"[ResetPassword] Calling extend.microsoft.modify_password for DN: {user_dn}",
            level="debug",
        )
        try:
            self.client.extend.microsoft.modify_password(user_dn, new_password)
        except LDAPException as e:
            self.log(f"[ResetPassword] LDAPException during modify_password: {e}", level="error")
            raise Exception(f"Failed to reset password for account {username}: {e}") from e

        self.log(
            f"[ResetPassword] modify_password LDAP result: {self.client.result}",
            level="debug",
        )

        if self.client.result.get("description") != "success":
            raise Exception(f"Password reset failed for {username}: {self.client.result.get('description')}")

    def run(self, arguments: ResetPassUserArguments):
        self.log(
            f"[ResetPassword] Starting password reset for user: {arguments.username}",
            level="info",
        )
        self.log(f"[ResetPassword] Search base (basedn): {arguments.basedn}", level="debug")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn, arguments.email)
        self.log(
            f"[ResetPassword] search_userdn_query returned {len(user_query)} result(s)",
            level="debug",
        )

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1 and not arguments.apply_to_all:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        if len(user_query) == 1 and not arguments.apply_to_all:
            user_dn = user_query[0][0]
            self.log(f"[ResetPassword] Resolved DN: {user_dn}", level="debug")
            self._reset_password_for_user(user_dn, arguments.username, arguments.new_password)
            self.log(
                f"[ResetPassword] Password reset successful for user: {arguments.username}",
                level="info",
            )
            return None

        results: list[dict] = []
        for user_dn, _ in user_query:
            self.log(f"[ResetPassword] Resolved DN: {user_dn}", level="debug")
            try:
                self._reset_password_for_user(user_dn, arguments.username, arguments.new_password)
                results.append({"dn": user_dn, "status": "success"})
                self.log(f"[ResetPassword] Password reset successful for user: {user_dn}", level="info")
            except Exception as e:
                results.append({"dn": user_dn, "status": "failed", "error": str(e)})
                self.log(f"[ResetPassword] Password reset failed for user {user_dn}: {e}", level="error")

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

    def _enable_user(self, user_dn: str, current_uac: int | None, username: str | None) -> None:
        uac_disabled = 2
        uac = current_uac if current_uac is not None else DEFAULT_UAC
        self.log(f"[EnableUser] Current UAC: {uac} (binary: {bin(uac)})", level="debug")
        new_uac = uac & ~uac_disabled
        self.log(
            f"[EnableUser] New UAC after clearing ACCOUNTDISABLE bit: {new_uac} (binary: {bin(new_uac)})",
            level="debug",
        )
        self.log(f"[EnableUser] Calling client.modify for DN: {user_dn}", level="debug")

        try:
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", new_uac)]}, None)
        except LDAPException as e:
            self.log(f"[EnableUser] LDAPException during modify: {e}", level="error")
            raise Exception(f"Failed to enable {username} account: {e}") from e

        self.log(f"[EnableUser] modify LDAP result: {self.client.result}", level="debug")

        if self.client.result.get("description") != "success":
            raise Exception(f"Enable action failed for {username}: {self.client.result.get('description')}")

    def run(self, arguments: UserAccountArguments):
        self.log(
            f"[EnableUser] Starting enabling user account: {arguments.username}",
            level="info",
        )
        self.log(f"[EnableUser] Search base (basedn): {arguments.basedn}", level="debug")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn, arguments.email)
        self.log(
            f"[EnableUser] search_userdn_query returned {len(user_query)} result(s)",
            level="debug",
        )

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1 and not arguments.apply_to_all:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        if len(user_query) == 1 and not arguments.apply_to_all:
            user_dn = user_query[0][0]
            current_uac = user_query[0][1]
            self.log(f"[EnableUser] Resolved DN: {user_dn}", level="debug")
            self._enable_user(user_dn, current_uac, arguments.username)
            self.log(f"[EnableUser] User {arguments.username} enabled successfully", level="info")
            return None

        results: list[dict] = []
        for user_dn, current_uac in user_query:
            self.log(f"[EnableUser] Resolved DN: {user_dn}", level="debug")
            try:
                self._enable_user(user_dn, current_uac, arguments.username)
                results.append({"dn": user_dn, "status": "success"})
                self.log(f"[EnableUser] User {user_dn} enabled successfully", level="info")
            except Exception as e:
                results.append({"dn": user_dn, "status": "failed", "error": str(e)})
                self.log(f"[EnableUser] Failed to enable user {user_dn}: {e}", level="error")

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

    def _disable_user(self, user_dn: str, current_uac: int | None, username: str | None) -> None:
        uac_disabled = 2
        uac = current_uac if current_uac is not None else DEFAULT_UAC
        self.log(f"[DisableUser] Current UAC: {uac} (binary: {bin(uac)})", level="debug")
        new_uac = uac | uac_disabled
        self.log(
            f"[DisableUser] New UAC after setting ACCOUNTDISABLE bit: {new_uac} (binary: {bin(new_uac)})",
            level="debug",
        )
        self.log(f"[DisableUser] Calling client.modify for DN: {user_dn}", level="debug")

        try:
            self.client.modify(user_dn, {"userAccountControl": [("MODIFY_REPLACE", new_uac)]}, None)
        except LDAPException as e:
            self.log(f"[DisableUser] LDAPException during modify: {e}", level="error")
            raise Exception(f"Failed to disable {username} account: {e}") from e

        self.log(f"[DisableUser] modify LDAP result: {self.client.result}", level="debug")

        if self.client.result.get("description") != "success":
            raise Exception(f"Disable action failed for {username}: {self.client.result.get('description')}")

    def run(self, arguments: UserAccountArguments):
        self.log(
            f"[DisableUser] Starting disable action for user: {arguments.username}",
            level="info",
        )
        self.log(f"[DisableUser] Search base (basedn): {arguments.basedn}", level="debug")

        user_query = self.search_userdn_query(arguments.username, arguments.basedn, arguments.email)
        self.log(
            f"[DisableUser] search_userdn_query returned {len(user_query)} result(s)",
            level="debug",
        )

        if len(user_query) == 0:
            raise Exception(f"User not found: {arguments.username}")

        if len(user_query) > 1 and not arguments.apply_to_all:
            raise Exception(f"Multiple users found with name: {arguments.username}, count: {len(user_query)}")

        if len(user_query) == 1 and not arguments.apply_to_all:
            user_dn = user_query[0][0]
            current_uac = user_query[0][1]
            self.log(f"[DisableUser] Resolved DN: {user_dn}", level="debug")
            self._disable_user(user_dn, current_uac, arguments.username)
            self.log(
                f"[DisableUser] User {arguments.username} has been disabled successfully",
                level="info",
            )
            return None

        results: list[dict] = []
        for user_dn, current_uac in user_query:
            self.log(f"[DisableUser] Resolved DN: {user_dn}", level="debug")
            try:
                self._disable_user(user_dn, current_uac, arguments.username)
                results.append({"dn": user_dn, "status": "success"})
                self.log(f"[DisableUser] User {user_dn} has been disabled successfully", level="info")
            except Exception as e:
                results.append({"dn": user_dn, "status": "failed", "error": str(e)})
                self.log(f"[DisableUser] Failed to disable user {user_dn}: {e}", level="error")

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
