from glimps.base import GlimpsAction
from glimps.models import AnalysisResponse, GetAnalysisByUUIDArgument


class RetrieveAnalysis(GlimpsAction):
    """Action to get a result by uuid"""

    name = "Retrieve analysis"
    description = "Retrieve the analysis matching the given uuid"
    results_model = AnalysisResponse

    def run(self, arguments: GetAnalysisByUUIDArgument) -> AnalysisResponse:
        analysis = self.gdetect_client.get_by_uuid(arguments.uuid)
        response = AnalysisResponse.parse_obj(analysis)
        return response
