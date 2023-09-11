from github_modules.audit_log_trigger import AuditLogConnector, GithubModule

if __name__ == "__main__":
    module = GithubModule()
    module.register(AuditLogConnector, "github_audit_logs")
    module.run()
