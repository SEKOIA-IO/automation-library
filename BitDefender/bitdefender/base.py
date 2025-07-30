from functools import cached_property

from sekoia_automation.action import Action
from bitdefender.client import ApiClient
from requests import Response
import uuid

from .logging import get_logger
from .helpers import handle_uri

logger = get_logger()

class BitdefenderAction(Action):
    endpoint_api: str
    method_name: str

    @cached_property
    def api_key(self):
        return self.module.configuration["api_key"]
    
    @cached_property
    def api_url(self):
        return handle_uri(self.module.configuration["url"])
    
    @cached_property
    def client(self):
        return ApiClient(
            instance_url=self.module.configuration["url"],
            api_key=self.module.configuration["api_key"],
            nb_retries=5,
            ratelimit_per_second=10,
        )
    
    def get_api_url(self) -> str:
        return f"{self.api_url}/{self.endpoint_api}"
    
    def _handle_response_error(self, response: Response) -> None:
        if not response.ok:
            logger.error(
                "Failed request to Bitdefender API",
                status_code=response.status_code,
                reason=response.reason,
                error=response.content,
            )

            message = f"Request to Bitdefender API failed with status {response.status_code} - {response.reason}"
            self.log(message=message, level="error")
            response.raise_for_status()
    
    def run(self, arguments: dict) -> dict:
        if not self.endpoint_api or not self.method_name:
            raise ValueError("Endpoint API and method name must be defined.")
        
        url = self.get_api_url()
        body = {
            "jsonrpc": "2.0",
            "method": self.method_name,
            "params": arguments,
            "id": str(uuid.uuid4()),
        }

        response = self.client.post(
            url,
            json=body
        )
        
        if not response.ok:
            self._handle_response_error(response)
        
        return response.json()