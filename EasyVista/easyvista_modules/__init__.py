from sekoia_automation.module import Module

from easyvista_modules.models import EasyVistaConfiguration


class EasyVistaModule(Module):
    configuration: EasyVistaConfiguration  # type: ignore[override]
