from sekoia_automation.checkpoint import CheckpointCursor


class LastFileIdCursor(CheckpointCursor):
    def get_next_file_name(self, skip_files: int = 0):
        pass

    def get_counter(self) -> int:
        _, counter = self.offset.split("_")
        return int(counter)
