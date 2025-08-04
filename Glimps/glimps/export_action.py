from glimps.base import GLIMPSAction
from glimps.models import ExportSubmissionArguments


class ExportSubmission(GLIMPSAction):
    """Action to export analysis result with the requested layout and format"""

    name = "Export analysis result"
    description = "Export analysis result with the requested layout and format"

    def run(self, arguments: ExportSubmissionArguments) -> bytes:
        # send the request to Glimps
        response = self.gdetect_client.export_result(
            uuid=arguments.uuid,
            format=arguments.format,
            layout=arguments.layout,
            full=arguments.is_full,
        )
        return response
