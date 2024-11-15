from glimps.models import GlimpsModule

from glimps.submit_file_to_be_analysed_action import SubmitFileToBeAnalysed
from glimps.get_status_action import GetStatus
from glimps.retrieve_analysis_action import RetrieveAnalysis
from glimps.export_action import ExportSubmission
from glimps.search_analysis_by_sha256_action import SearchPreviousAnalysis
from glimps.submit_file_to_be_analysed_action import SubmitFileWaitForResult


if __name__ == "__main__":
    module = GlimpsModule()
    module.register(SubmitFileToBeAnalysed, "SubmitFileToBeAnalysed")
    module.register(GetStatus, "GetStatus")
    module.register(RetrieveAnalysis, "RetrieveAnalysis")
    module.register(ExportSubmission, "ExportSubmission")
    module.register(SearchPreviousAnalysis, "SearchPreviousAnalysis")
    module.register(SubmitFileWaitForResult, "SubmitFileWaitForResult")
    module.run()
