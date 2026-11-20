from sekoia_automation.module import Module

from ssh_remote.models import SSHModuleConfiguration


class SSHModule(Module):
    configuration: SSHModuleConfiguration
