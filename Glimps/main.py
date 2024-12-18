from glimps.models import GLIMPSModule
from sekoia_automation.module import Module

from glimps.export_action import ExportSubmission
from glimps.search_analysis_by_sha256_action import SearchPreviousAnalysis
from glimps.submit_file_to_be_analysed_action import WaitForFile
from glimps.submit_file_to_be_analysed_action import SubmitFile
from glimps.get_status_action import GetStatus
from glimps.retrieve_analysis_action import RetrieveAnalysis
from glimps.deprecated import (
    DeprecatedRetrieveAnalysis,
    DeprecatedSearchPreviousAnalysis,
    DeprecatedSubmitFileToBeAnalysed,
)

if __name__ == "__main__":
    deprecated_module = Module()
    deprecated_module.register(DeprecatedRetrieveAnalysis)
    deprecated_module.register(DeprecatedSearchPreviousAnalysis)
    deprecated_module.register(DeprecatedSubmitFileToBeAnalysed)
    deprecated_module.run()

    module = GLIMPSModule()
    module.register(ExportSubmission)
    module.register(SearchPreviousAnalysis)
    module.register(WaitForFile)
    module.register(SubmitFile)
    module.register(GetStatus)
    module.register(RetrieveAnalysis)
    module.run()
