from pathlib import Path


from .actions_json import ActionsJSONValidator
from .changelog import ChangelogValidator
from .connectors_json import ConnectorsJSONValidator
from .dockerfile import DockerfileValidator
from .logo import LogoValidator
from .manifest import ManifestValidator
from .tests import TestsValidator
from .triggers_json import TriggersJSONValidator

from .module import ModuleValidator

MODULES_PATH = Path(__file__).parent.parent.parent.parent
