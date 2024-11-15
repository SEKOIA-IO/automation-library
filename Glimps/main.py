from glimps.models import GLIMPSModule

from glimps.export_action import ExportSubmission
from glimps.search_analysis_by_sha256_action import SearchPreviousAnalysis
from glimps.submit_file_to_be_analysed_action import WaitForFile
from glimps.submit_file_to_be_analysed_action import SubmitFile
from glimps.get_status_action import GetStatus
from glimps.retrieve_analysis_action import RetrieveAnalysis


if __name__ == "__main__":
    module = GLIMPSModule()
    module.register(ExportSubmission, "ExportSubmission")
    module.register(SearchPreviousAnalysis, "SearchPreviousAnalysis")
    module.register(WaitForFile, "WaitForFile")
    module.register(SubmitFile, "SubmitFile")
    module.register(GetStatus, "GetStatus")
    module.register(RetrieveAnalysis, "RetrieveAnalysis")
    module.run()
