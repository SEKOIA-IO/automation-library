from typing import Any, Optional

from sekoia_automation.action import Action
from thehive4py import TheHiveApi
from thehive4py.types.alert import InputAlert, OutputAlert
from requests import HTTPError
from posixpath import join as urljoin

from .thehiveconnector import prepare_verify_param


class TheHiveCreateAlertV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[OutputAlert]:
        base_url = self.module.configuration["base_url"]
        organisation = self.module.configuration["organisation"]
        verify_certificate = self.module.configuration.get("verify_certificate", True)
        ca_certificate = self.module.configuration.get("ca_certificate")

        self.log(
            f"[CreateAlert] Initializing TheHive API — url={base_url} organisation={organisation}",
            level="debug",
        )
        self.log(
            f"[CreateAlert] verify_certificate={verify_certificate} ca_certificate={'<provided>' if ca_certificate else '<not set>'}",
            level="debug",
        )

        verify_param = prepare_verify_param(verify_certificate, ca_certificate, log_fn=self.log)
        self.log(f"[CreateAlert] verify param resolved to: {verify_param!r}", level="debug")

        try:
            api = TheHiveApi(
                base_url,
                self.module.configuration["apikey"],
                organisation=organisation,
                verify=verify_param,
            )
            self.log("[CreateAlert] TheHiveApi instance created successfully", level="debug")
        except Exception as exc:
            self.log(
                f"[CreateAlert] Failed to create TheHiveApi ({type(exc).__name__}): {exc}",
                level="error",
            )
            self.error(str(exc))
            return None

        arg_sekoia_server = arguments.get("sekoia_base_url", "https://app.sekoia.io")
        arg_alert = arguments["alert"]

        alert_type = f"{arg_alert['alert_type']['category']}/{arg_alert['alert_type']['value']}"
        if len(alert_type) > 32:
            alert_type = arg_alert["alert_type"]["category"][:32]  # limit to 32 char, max of thehive api

        link = urljoin(arg_sekoia_server.rstrip("/"), f"/operations/alerts/{arg_alert['short_id']}")

        self.log(
            f"[CreateAlert] Building alert — title={arg_alert['title']!r} type={alert_type!r} sourceRef={arg_alert['short_id']!r}",
            level="debug",
        )

        alert: InputAlert = InputAlert(
            severity=arg_alert["urgency"]["severity"] // 25 + 1,  # from 0-100 to 1-4
            date=arg_alert["created_at"] * 1000,  # date in ms for TheHive instead of sec in Sekoia
            tags=[],
            externalLink=link,
            title=arg_alert["title"],
            type=alert_type,
            source="Sekoia.io",
            sourceRef=arg_alert["short_id"],
            # add full alert type in description, add link in description
            description=f"type: {alert_type}\r\nlink: {link}\r\ndetails: {arg_alert['details']}",
        )

        if arguments.get("tlp") is not None:
            alert["tlp"] = int(arguments["tlp"])
            self.log(f"[CreateAlert] TLP set to: {alert['tlp']}", level="debug")

        if arguments.get("pap") is not None:
            alert["pap"] = int(arguments["pap"])
            self.log(f"[CreateAlert] PAP set to: {alert['pap']}", level="debug")

        self.log("[CreateAlert] Calling api.alert.create", level="debug")
        try:
            response = api.alert.create(alert=alert)
            self.log(
                f"[CreateAlert] Alert created successfully — id={response.get('_id', '?')}",
                level="info",
            )
            return response
        except HTTPError as e:
            self.log(
                f"[CreateAlert] HTTPError ({type(e).__name__}): {e}",
                level="error",
            )
            self.error(str(e))
            if e.response is not None:
                self.log(
                    f"[CreateAlert] Status code: {e.response.status_code}",
                    level="error",
                )
                self.log(f"[CreateAlert] Response body: {e.response.text}", level="error")
        except Exception as e:
            self.log(
                f"[CreateAlert] Unexpected error ({type(e).__name__}): {e}",
                level="error",
            )
            self.error(str(e))

        return None
