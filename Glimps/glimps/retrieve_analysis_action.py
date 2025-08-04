from glimps.base import GLIMPSAction
from glimps.models import AnalysisDetails, GetAnalysisByUUIDArgument, AnalysisResponse


class RetrieveAnalysis(GLIMPSAction):
    """Action to get a result by uuid"""

    name = "Retrieve analysis"
    description = "Retrieve the analysis matching the given uuid"
    results_model = AnalysisResponse

    def run(self, arguments: GetAnalysisByUUIDArgument) -> AnalysisResponse:
        raw_analysis = self.gdetect_client.get_by_uuid(arguments.uuid)
        details = AnalysisDetails.parse_obj(raw_analysis)
        view_token: str = self._get_token_view_url(raw_analysis)

        return AnalysisResponse(analysis=details, view_url=view_token)
