from glimps.models import GlimpsModule

from glimps.submit_file_to_be_analysed_action import SubmitFileWaitForResult
from glimps.search_analysis_by_sha256_action import SearchPreviousAnalysis
from glimps.get_status_action import GetStatus
from glimps.submit_file_to_be_analysed_action import SubmitFileToBeAnalysed
from glimps.retrieve_analysis_action import RetrieveAnalysis


if __name__ == "__main__":
    module = GlimpsModule()
    module.register(SubmitFileWaitForResult, "SubmitFileWaitForResult")
    module.register(SearchPreviousAnalysis, "SearchPreviousAnalysis")
    module.register(GetStatus, "GetStatus")
    module.register(SubmitFileToBeAnalysed, "SubmitFileToBeAnalysed")
    module.register(RetrieveAnalysis, "RetrieveAnalysis")
    module.run()
