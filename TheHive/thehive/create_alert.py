from typing import Any

from sekoia_automation.action import Action
from thehive4py.api import TheHiveApi
from thehive4py.models import Alert, AlertArtifact
from requests import HTTPError

THEHIVE_TYPES = [
    "autonomous-system",
    "domain",
    "file",
    "filename",
    "fqdn",
    "hash",
    "hostname",
    "ip",
    "mail",
    "mail-subject",
    "other",
    "regexp",
    "registry",
    "uri_path",
    "url",
    "user-agent",
]


ECS_TO_THEHIVE: dict[str, str] = {
    "source.domain": "domain",
    "source.subdomain": "domain",
    "source.top_level_domain": "domain",
    "source.registered_domain": "domain",
    "destination.domain": "domain",
    "destination.subdomain": "domain",
    "destination.top_level_domain": "domain",
    "destination.registered_domain": "domain",
    "server.domain": "domain",
    "server.registered_domain": "domain",
    "server.subdomain": "domain",
    "server.top_level_domain": "domain",
    "url.domain": "domain",
    "url.subdomain": "domain",
    "url.top_level_domain": "domain",
    "url.registered_domain": "domain",
    "file.name": "filename",
    "dll.name": "filename",
    "hash.md5": "hash",
    "hash.sha1": "hash",
    "hash.sha256": "hash",
    "hash.sha512": "hash",
    "source.ip": "ip",
    "source.nat.ip": "ip",
    "destination.ip": "ip",
    "destination.nat.ip": "ip",
    "network.forwarded_ip": "ip",
    "server.ip": "ip",
    "server.nat.ip": "ip",
    "email.from.address": "mail",
    "email.to.address": "mail",
    "email.reply_to.address": "mail",
    "email.subject": "mail-subject",
    "registry.path": "registry",
    "url.full": "url",
    "url.original": "url",
    "user_agent.original": "user-agent",
    "host.name": "hostname",
    "log.hostname": "hostname",
    "host.hostname": "hostname",
    "user.name": "other",
    "host.user.name": "other",
    "user.full_name": "other",
}


class TheHiveCreateAlert(Action):
    def run(self, arguments: dict[str, Any]):
        api = TheHiveApi(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        arg_alert = arguments["alert"]
        arg_events = arguments.get("events", [])

        artifacts: list[AlertArtifact] = []
        previous_value = []
        for event in arg_events:
            for key, values in event.items():
                if key in ECS_TO_THEHIVE:
                    for value in values if isinstance(values, list) else [values]:
                        if value not in previous_value:
                            artifacts.append(
                                AlertArtifact(
                                    dataType=ECS_TO_THEHIVE[key],
                                    tlp=arguments.get("artifact_tlp", 1),
                                    ioc=False,  # True only if we can check it came from the IC
                                    sighted=arguments.get("artifact_sighted", True),
                                    ignoreSimilarity=arguments.get("artifact_ignore_similarity", True),
                                    tags=[f"sekoia:type={key}"],
                                    data=value,
                                )
                            )
                            previous_value.append(value)

        alert_type = f"{arg_alert['alert_type']['category']}/{arg_alert['alert_type']['value']}"
        if len(alert_type) > 32:
            alert_type = arg_alert["alert_type"]["category"][:32]  # limit to 32 char, max of thehive api
        link = f"https://app.sekoia.io/operations/alerts/{arg_alert['short_id']}"
        alert: Alert = Alert(
            id=arg_alert["uuid"],
            severity=arg_alert["urgency"]["severity"] // 25 + 1,  # from 0-100 to 1-4
            date=arg_alert["created_at"] * 1000,  # date in ms for TheHive instead of sec in Sekoia
            tags=[],
            title=arg_alert["title"],
            type=alert_type,
            source="Sekoia.io",
            sourceRef=arg_alert["short_id"],
            externalLink=link,
            description=f"type: {alert_type}\r\nlink: {link}\r\ndetails: {arg_alert['details']}",  # add full alert type in description, add link in description
            artifacts=artifacts,
        )

        try:
            response = api.create_alert(alert)
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            self.error(str(e))
            if e.response is not None:
                self.log(f"Status code: {e.response.status_code}")
                self.log(f"Response: {e.response.text}")
        except Exception as e:
            self.error(str(e))
        return None
