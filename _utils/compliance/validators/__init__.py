from pathlib import Path

from .actions_json import ActionsJSONValidator
from .changelog import ChangelogValidator
from .connectors_json import ConnectorsJSONValidator
from .deps import DependenciesValidator
from .dockerfile import DockerfileValidator
from .logo import LogoValidator
from .main import MainPYValidator
from .manifest import ManifestValidator
from .tests import TestsValidator
from .triggers_json import TriggersJSONValidator

from .module import ModuleValidator

MODULES_PATH = Path(__file__).parent.parent.parent.parent
