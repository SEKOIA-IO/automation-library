import argparse
from pathlib import Path

from . import (
    ActionsJSONValidator,
    ChangelogValidator,
    ConnectorsJSONValidator,
    DependenciesValidator,
    DockerfileValidator,
    LogoValidator,
    MainPYValidator,
    ManifestValidator,
    TestsValidator,
    TriggersJSONValidator,
)
from .models import CheckResult


class ModuleValidator:
    def __init__(self, path: Path, args: argparse.Namespace) -> None:
        self.path = path
        self.args = args

        module_name = path.name
        self.result = CheckResult(
            name=f"check_module_{module_name}",
            description="Checks the module has a proper definition",
            options={"path": path},
        )

        self.validators = [
            TestsValidator,
            ChangelogValidator,
            ManifestValidator,
            DependenciesValidator,
            LogoValidator,
            DockerfileValidator,
            ActionsJSONValidator,
            ConnectorsJSONValidator,
            TriggersJSONValidator,
            MainPYValidator,
        ]

    def validate(self):
        for validator in self.validators:
            validator.validate(self.result, self.args)

    def __repr__(self):
        return f'ModuleValidator(path="{self.path}")'
