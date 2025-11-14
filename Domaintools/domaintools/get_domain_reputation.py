from typing import Any
import json
from sekoia_automation.action import Action
from .models import DomainToolsConfig, DomainToolsError, DomaintoolsrunAction

class DomaintoolsDomainReputation(Action):
    def run(self, arguments: dict[str, Any]) -> str:
        try:
            config = DomainToolsConfig(
                api_username=self.module.configuration["api_username"],
                api_key=self.module.configuration["api_key"],
                host="https://api.domaintools.com/"
            )

            parsed_args: dict[str, Any] = {
                "domain": arguments.get("domain"),
                "ip": arguments.get("ip", "192.168.0.1"),
                "email": arguments.get("email", "admin@example.com"),
                "domaintools_action": "domain_reputation",
            }
            #print(f"Parsed arguments: {parsed_args}")  # Debugging line

            response = DomaintoolsrunAction(config, parsed_args)
            print(f"API call response: {response}")  # Debugging line
            return response

        except DomainToolsError as e:
            print(json.dumps({"error": f"DomainTools client initialization error: {e}"}, indent=2))
        except Exception as e:
            print(json.dumps({"error": f"Unexpected initialization error: {e}"}, indent=2))
        
        return None
