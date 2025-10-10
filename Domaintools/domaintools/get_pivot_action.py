from typing import Any
import json
from sekoia_automation.action import Action
from .models import DomainToolsConfig, DomainToolsError, DomaintoolsrunAction

class DomaintoolsPivotAction(Action):
    def run(self, arguments: dict[str, Any]) -> str:
        try:
            config = DomainToolsConfig(
                api_username=self.module.configuration["api_username"],
                api_key=self.module.configuration["api_key"],
                host="https://api.domaintools.com/"
            )

            parsed_args: dict[str, Any] = {
                "domain": arguments.get("domain"),
                "ip": arguments.get("ip"),
                "email": arguments.get("email"),
                "domaintools_action": "pivot_action",
            }

            result = DomaintoolsrunAction(config, parsed_args)
            return result

        except DomainToolsError as e:
            print(json.dumps({"error": f"DomainTools client initialization error: {e}"}, indent=2))
        except Exception as e:
            print(json.dumps({"error": f"Unexpected initialization error: {e}"}, indent=2))
        
        return None
