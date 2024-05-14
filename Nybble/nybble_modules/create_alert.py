from json import JSONEncoder
from math import ceil
from pydantic import BaseModel, Field
import requests
from requests import Response
from nybble_modules import NybbleAction


class CreateAlertArguments(BaseModel):
    alert_data: dict = Field(..., description="Received alert, from Sekoia 'Get Alert' action")
    events: list[dict] = Field(..., description="Related Events, from Sekoia 'Get The Alert Events' action")


class CreateAlertResults(BaseModel):
    status: bool
    details: str


class NybbleAlert(dict):
    """
    Final Object sent to Nybble Hub
    """

    alert_processing_time: str
    alert_fields: dict[str, str]
    alert_event_original: dict
    alert_id: str
    alert_level: int
    rule_status: str
    rule_name: str
    rule_tags: list[str]
    rule_references: list[str]
    sigma_rule_id: str
    mssp_client: str
    custom_fields_visible: dict
    custom_fields_hidden: dict


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
            nybble_fields[cur_field] = event[cur_field]
        return nybble_fields

    def _cleanEventOriginal(self, original_event: dict) -> dict:
        """
        remove sekoiaio.xxx fields and rename timestamp -> @timestamp
        """
        cleaned_event = {k: v for k, v in original_event.items() if not str(k).startswith("sekoiaio")}
        cleaned_event["@timestamp"] = cleaned_event.pop("timestamp")

        return cleaned_event

    def _getRuleDefinition(self, rule_uuid: str, api_key: str, base_url: str) -> dict:
        """
        Returns the rule from the rules catalog
        """

        url = f"{base_url}v1/sic/conf/rules-catalog/rules/{rule_uuid}"

        response: Response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        return response.json()

    def run(self, arguments: CreateAlertArguments) -> CreateAlertResults:
        nybble_alert = NybbleAlert()
        self.log(message=f"Sending alert to Nybble Hub. Alert ID: {arguments.alert_data['uuid']}", level="info")

        """
    Get rule from rule Catalog -> provide fields, references etc...
    """
        rule_definition = self._getRuleDefinition(
            rule_uuid=arguments.alert_data["rule"]["uuid"],
            api_key=self.module.configuration.sekoia_api_key,
            base_url=self.module.configuration.sekoia_url,
        )

        """
    Generate final payload for Nybble Hub
      We take only the 1st event triggering the alert
    """
        nybble_alert.alert_processing_time = arguments.alert_data["created_at"]
        nybble_alert.alert_fields = self._generateFields(
            rule_event_fields=rule_definition["event_fields"], event=arguments.events[0]
        )
        nybble_alert.alert_event_original = self._cleanEventOriginal(arguments.events[0])
        nybble_alert.alert_id = arguments.alert_data["uuid"]
        nybble_alert.alert_level = (
            1 if arguments.alert_data["urgency"]["value"] == 0 else ceil(arguments.alert_data["urgency"]["value"] / 25)
        )  # scale 1 to 100 in sekoia -> 1 to 4 in Nybble
        nybble_alert.rule_status = "stable"
        nybble_alert.rule_name = arguments.alert_data["title"]
        nybble_alert.rule_references = str(rule_definition["references"]).split(
            ","
        )  # sekoia is providing comma separated references
        nybble_alert.rule_tags = self._generateTags(rule_definition["tags"])
        nybble_alert.sigma_rule_id = rule_definition[
            "uuid"
        ]  # TODO find better (we took RULE uuid instead of uuid_instance which is coming from alert)
        nybble_alert.mssp_client = arguments.alert_data["community_uuid"]
        nybble_alert.custom_fields_visible = {"false_positives": rule_definition["false_positives"]}
        nybble_alert.custom_fields_hidden = {}

        print(nybble_alert.alert_event_original)

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
