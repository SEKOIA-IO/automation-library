from collections.abc import Generator

from cached_property import cached_property
from mwdblib import Malwarecage, MalwarecageConfig
from sekoia_automation.trigger import Trigger


class MWDBTrigger(Trigger):
    """
    Base class for MWDB triggers.
    """

    @property
    def api_key(self):
        return self.module.configuration["api_key"]

    @cached_property
    def client(self) -> Malwarecage:
        return Malwarecage(api_key=self.api_key)

    def listen(self) -> Generator:
        """
        Listen for changes for the given object
        """
        raise NotImplementedError()

    def run(self):
        self.log("Trigger starting")
        try:
            for obj in self.listen():
                self.handle(obj)
        finally:
            self.log("Trigger stopping")

    def handle(self, obj: MalwarecageConfig):
        raise NotImplementedError()


class MWDBConfigsTrigger(MWDBTrigger):
    def listen(self):
        return self.client.listen_for_configs()

    def handle(self, config: MalwarecageConfig):
        files = self.get_files_from_config(config)

        config_dict = config.data

        # Clean non serializable objects
        if "config" in config_dict:
            del config_dict["config"]

        config_dict["files"] = files
        self.log(
            f"Sending new config: {config_dict['family']} ({config_dict['config_type']})",
            level="debug",
        )
        self.send_event(
            f"MWDB config: {config_dict['family']} ({config_dict['config_type']})",
            config_dict,
        )

    def get_files_from_config(self, config: MalwarecageConfig) -> list[dict]:
        """
        Get the files linked to the given config
        """
        files = []
        fields = [
            "file_name",
            "file_size",
            "file_type",
            "ssdeep",
            "md5",
            "sha1",
            "sha256",
            "sha512",
            "crc32",
        ]
        for f in config.parents:
            item = {}
            for field in fields:
                if hasattr(f, field):
                    item[field] = getattr(f, field)
            files.append(item)
        return files
