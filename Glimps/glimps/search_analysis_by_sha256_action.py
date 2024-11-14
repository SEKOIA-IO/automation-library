from glimps.base import GlimpsAction
from glimps.models import AnalysisResponse, SearchAnalysisBySha256Argument


class SearchPreviousAnalysis(GlimpsAction):
    """Action to search an analysis result using the file sha256"""

    name = "Search analysis"
    description = "Search an analysis for a given sha256 input file"
    results_model = AnalysisResponse

    def run(self, arguments: SearchAnalysisBySha256Argument) -> AnalysisResponse:
        analysis = self.gdetect_client.get_by_sha256(arguments.sha256)
        response: AnalysisResponse = AnalysisResponse.parse_obj(analysis)
        return response
