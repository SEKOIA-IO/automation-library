from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.default_query_parameters import QueryParameters
from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption

from .base import ApplicationArguments, MicrosoftGraphAction


class DeleteApplicationAction(MicrosoftGraphAction):
    name = "Delete application"
    description = (
        "Delete an application object. Requires the Application.ReadWrite.OwnedBy or Application.ReadWrite.All."
    )

    async def query_delete_app(
        self, application_id: str, req_conf: RequestConfiguration[QueryParameters]
    ) -> None:  # pragma: no cover
        return await self.client.applications.by_application_id(application_id).delete(request_configuration=req_conf)

    async def run(self, arguments: ApplicationArguments) -> None:
        request_configuration: RequestConfiguration[QueryParameters] = RequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())]
        )

        application_id = arguments.objectId
        if not application_id:
            raise ValueError("The objectId is required.")

        # Returns None based on docs, but raises if error
        await self.query_delete_app(application_id, request_configuration)
