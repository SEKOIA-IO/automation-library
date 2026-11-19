from sekoia_automation.module import Module

from mimecast_modules import MimecastModule
from mimecast_modules.models import MimecastModuleConfiguration


def test_mimecast_module_definition() -> None:
    assert issubclass(MimecastModule, Module)
    assert MimecastModule.__annotations__["configuration"] is MimecastModuleConfiguration
