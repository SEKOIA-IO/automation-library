from sekoia_automation.module import Module

from polyswarm_modules.models import PolyswarmModuleConfiguration


class PolyswarmModule(Module):
    # The SDK types the configuration setter loosely. Narrowing it to this
    # module's model is the point of the subclass, so the override stands.
    configuration: PolyswarmModuleConfiguration  # type: ignore[assignment,override]
