from sekoia_automation.module import Module

from glimps import RetrieveAnalysis, SearchPreviousAnalysis, SubmitFileToBeAnalysed

if __name__ == "__main__":
    module = Module()
    module.register(RetrieveAnalysis, "get-results/{uuid}")
    module.register(SearchPreviousAnalysis, "get-search/{sha256}")
    module.register(SubmitFileToBeAnalysed, "post-submit")
    module.run()
