from sekoia_automation.module import Module

from github_modules.models import GithubModuleConfiguration


class GithubModule(Module):
    configuration: GithubModuleConfiguration
