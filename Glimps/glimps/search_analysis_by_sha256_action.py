from glimps.base import GLIMPSAction
from glimps.models import (
    AnalysisDetails,
    SearchAnalysisBySha256Argument,
    AnalysisResponse,
)


class SearchPreviousAnalysis(GLIMPSAction):
    """Action to search an analysis result using the file sha256"""

    name = "Search analysis"
    description = "Search an analysis for a given sha256 input file"
    results_model = AnalysisResponse

    def run(self, arguments: SearchAnalysisBySha256Argument) -> AnalysisResponse:
        raw_analysis = self.gdetect_client.get_by_sha256(arguments.sha256)
        details: AnalysisDetails = AnalysisDetails.parse_obj(raw_analysis)
        view_token: str = self._get_token_view_url(raw_analysis)

        return AnalysisResponse(analysis=details, view_url=view_token)
