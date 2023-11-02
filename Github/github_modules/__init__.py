"""Contains connector, trigger and implementation to interact with Github."""

from sekoia_automation.module import Module

from github_modules.models import GithubModuleConfiguration


class GithubModule(Module):
    """Configuration for Github module."""

    configuration: GithubModuleConfiguration
