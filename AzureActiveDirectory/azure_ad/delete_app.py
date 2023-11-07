import asyncio

from .base import MicrosoftGraphAction, ApplicationArguments

from kiota_abstractions.native_response_handler import NativeResponseHandler
from kiota_http.middleware.options import ResponseHandlerOption
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder


class DeleteApplicationAction(MicrosoftGraphAction):
    name = "Delete application"
    description = (
        "Delete an application object. Requires the Application.ReadWrite.OwnedBy or Application.ReadWrite.All."
    )

    async def query_delete_app(self, id, req_conf):
        return await self.client.applications.by_application_id(id).delete(request_configuration=req_conf)

    async def run(self, arguments: ApplicationArguments):
        request_configuration = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            options=[ResponseHandlerOption(NativeResponseHandler())],
        )

        response = await self.query_delete_app(arguments.objectId, request_configuration)

        response.raise_for_status()
