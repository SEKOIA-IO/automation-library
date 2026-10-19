from polyswarm_modules import PolyswarmModule
from polyswarm_modules.account_validator import PolyswarmAccountValidator
from polyswarm_modules.action_polyswarm_accountusage import AccountUsage
from polyswarm_modules.action_polyswarm_extractiocs import ExtractIocs
from polyswarm_modules.action_polyswarm_report import Report
from polyswarm_modules.action_polyswarm_sandboxfile import SandboxFile
from polyswarm_modules.action_polyswarm_sandboxip import SandboxIp
from polyswarm_modules.action_polyswarm_sandboxurl import SandboxUrl
from polyswarm_modules.action_polyswarm_scandomain import ScanDomain
from polyswarm_modules.action_polyswarm_scanfile import ScanFile
from polyswarm_modules.action_polyswarm_scanip import ScanIp
from polyswarm_modules.action_polyswarm_scanurl import ScanUrl
from polyswarm_modules.action_polyswarm_searchhash import SearchHash
from polyswarm_modules.action_polyswarm_searchhashes import SearchHashes
from polyswarm_modules.action_polyswarm_searchioc import SearchIoc
from polyswarm_modules.action_polyswarm_searchip import SearchIp
from polyswarm_modules.action_polyswarm_searchmetadata import SearchMetadata
from polyswarm_modules.action_polyswarm_searchurl import SearchUrl
from polyswarm_modules.connector_polyswarm_intel_feed import IntelFeed
from polyswarm_modules.trigger_polyswarm_sandbox_completed import SandboxCompleted

if __name__ == "__main__":
    module = PolyswarmModule()
    module.register_account_validator(PolyswarmAccountValidator)
    module.register(ScanUrl, "ScanUrl")
    module.register(ScanIp, "ScanIp")
    module.register(ScanDomain, "ScanDomain")
    module.register(ScanFile, "ScanFile")
    module.register(SearchHash, "SearchHash")
    module.register(SearchUrl, "SearchUrl")
    module.register(SearchIp, "SearchIp")
    module.register(SearchMetadata, "SearchMetadata")
    module.register(SearchIoc, "SearchIoc")
    module.register(SandboxFile, "SandboxFile")
    module.register(SandboxUrl, "SandboxUrl")
    module.register(SandboxIp, "SandboxIp")
    module.register(SearchHashes, "SearchHashes")
    module.register(ExtractIocs, "ExtractIocs")
    module.register(AccountUsage, "AccountUsage")
    module.register(Report, "Report")
    module.register(SandboxCompleted, "SandboxCompleted")
    module.register(IntelFeed, "polyswarm_intel_feed")
    module.run()
