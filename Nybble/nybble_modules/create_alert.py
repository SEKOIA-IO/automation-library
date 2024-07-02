from math import ceil
from pydantic import BaseModel, Field
import requests
from nybble_modules import NybbleAction


class CreateAlertArguments(BaseModel):
    alert_data: dict = Field(..., description="Received alert, from Sekoia 'Get Alert' action")
    rule: dict = Field(..., description="Alert Rule from Rule Catalog, from Sekoia 'Get Rule' action")
    events: list[dict] = Field(..., description="Related Events, from Sekoia 'Get The Alert Events' action")


class CreateAlertResults(BaseModel):
    status: bool
    details: str


class NybbleAlert(dict):
    """
    Final Object sent to Nybble Hub
    """

    def __init__(
        self,
        alert_processing_time=None,
        alert_fields=None,
        alert_event_original=None,
        alert_id=None,
        alert_level=None,
        rule_status=None,
        rule_name=None,
        rule_tags=None,
        rule_references=None,
        sigma_rule_id=None,
        mssp_client=None,
        custom_fields_visible=None,
        custom_fields_hidden=None,
    ):
        super().__init__()
        self["alert_processing_time"] = alert_processing_time
        self["alert_fields"] = alert_fields if alert_fields is not None else {}
        self["alert_event_original"] = alert_event_original if alert_event_original is not None else {}
        self["alert_id"] = alert_id
        self["alert_level"] = alert_level
        self["rule_status"] = rule_status
        self["rule_name"] = rule_name
        self["rule_tags"] = rule_tags if rule_tags is not None else []
        self["rule_references"] = rule_references if rule_references is not None else []
        self["sigma_rule_id"] = sigma_rule_id
        self["mssp_client"] = mssp_client
        self["custom_fields_visible"] = custom_fields_visible if custom_fields_visible is not None else {}
        self["custom_fields_hidden"] = custom_fields_hidden if custom_fields_hidden is not None else {}


class CreateAlertAction(NybbleAction):
    """
    Action to create an alert into Nybble Hub
    """

    name = "Create Alert"
    description = "Create an Alert into Nybble Hub"
    results_model = CreateAlertResults

    def _generateTags(self, rule_tags) -> list[str]:
        """
        generate tag array from rule catalog
        """
        if len(rule_tags) == 0:
            return []

        nybble_tags = list[str]()
        for tag in rule_tags:
            nybble_tags.append(tag["name"])
        return nybble_tags

    def _generateFields(self, rule_event_fields: list[dict], event: dict) -> dict[str, str]:
        """
        generate fields from highlighted fields in rule + current event
        """
        nybble_fields = dict[str, str]()

        #  Empty = host.name
        if len(rule_event_fields) == 0:
            return {"host.name": event["host.name"]}

        for field in rule_event_fields:
            cur_field = str(field["field"])
            valeur = event.get(cur_field)

            if valeur is not None:
                nybble_fields[cur_field] = valeur
        return nybble_fields

    def _cleanEventOriginal(self, original_event: dict) -> dict:
        """
        remove sekoiaio.xxx fields and rename timestamp -> @timestamp
        """
        cleaned_event = {k: v for k, v in original_event.items() if not str(k).startswith("sekoiaio")}
        cleaned_event["@timestamp"] = cleaned_event.pop("timestamp")

        return cleaned_event

    def run(self, arguments: CreateAlertArguments) -> CreateAlertResults:
        nybble_alert = NybbleAlert()
        self.log(message=f"Sending alert to Nybble Hub. Alert ID: {arguments.alert_data['uuid']}", level="info")

        """
    Generate final payload for Nybble Hub
      We take only the 1st event triggering the alert
    """
        nybble_alert["alert_processing_time"] = arguments.alert_data["created_at"]
        nybble_alert["alert_fields"] = self._generateFields(
            rule_event_fields=arguments.rule["event_fields"], event=arguments.events[0]
        )
        nybble_alert["alert_event_original"] = self._cleanEventOriginal(arguments.events[0])
        nybble_alert["alert_id"] = arguments.alert_data["uuid"]
        nybble_alert["alert_level"] = (
            1 if arguments.alert_data["urgency"]["value"] == 0 else ceil(arguments.alert_data["urgency"]["value"] / 25)
        )  # scale 1 to 100 in sekoia -> 1 to 4 in Nybble
        nybble_alert["rule_status"] = "stable"
        nybble_alert["rule_name"] = arguments.alert_data["title"]
        nybble_alert["rule_references"] = str(arguments.rule["references"]).split(
            ","
        )  # sekoia is providing comma separated references
        nybble_alert["rule_tags"] = self._generateTags(arguments.rule["tags"])
        nybble_alert["sigma_rule_id"] = arguments.rule[
            "uuid"
        ]  # TODO find better (we took RULE uuid instead of uuid_instance which is coming from alert)
        nybble_alert["mssp_client"] = arguments.alert_data["community_uuid"]
        nybble_alert["custom_fields_visible"] = {"false_positives": arguments.rule["false_positives"]}
        nybble_alert["custom_fields_hidden"] = {}

        """
    Send to Nybble Hub
    """
        nhub_conn_url = f"{self.module.configuration.nhub_url}/conn/sekoia"

        response = requests.post(
            nhub_conn_url,
            json=nybble_alert,
            auth=(f"{self.module.configuration.nhub_username}", f"{self.module.configuration.nhub_key}"),
        )

        if not response.ok:
            # Will end action as in error
            self.error(f"Send to Nybble Hub Failed: with {response.status_code}")

        return CreateAlertResults(
            status=response.ok,
            details=response.text,
        )
