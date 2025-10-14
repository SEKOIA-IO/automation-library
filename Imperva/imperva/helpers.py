import hashlib


class LogFileId:
    def __init__(self, prefix: str, counter: int) -> None:
        self.prefix = prefix
        self.counter = counter

    @classmethod
    def from_filename(cls, filename: str) -> "LogFileId":
        # 123_7.log
        log_name, counter = filename.removesuffix(".log").split("_")
        return LogFileId(prefix=log_name, counter=int(counter))

    def get_filename(self) -> str:
        return f"{self.prefix}_{self.counter}.log"

    def __hash__(self):
        return hash(self.get_filename())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LogFileId):
            raise NotImplementedError

        return self.counter == other.counter

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, LogFileId):
            raise NotImplementedError

        return self.counter < other.counter

    def __le__(self, other: object) -> bool:
        if not isinstance(other, LogFileId):
            raise NotImplementedError

        return self.counter <= other.counter

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, LogFileId):
            raise NotImplementedError

        return self.counter >= other.counter

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, LogFileId):
            raise NotImplementedError

        return self.counter > other.counter

    def __str__(self):
        return self.get_filename()


def is_compressed(content: bytes) -> bool:
    return content.startswith(b"\x78\x9c")


def extract_last_timestamp(file_content: bytes) -> int | None:
    file_split_content = file_content.split(b"|==|\n")
    # No header - no timestamp
    if len(file_split_content) != 2:
        return None

    # get the header section content
    file_header_content = file_split_content[0].decode("utf-8")

    end_time_idx = file_header_content.find("endTime:")
    if end_time_idx:
        end_time = int(file_header_content.split("endTime:")[1].splitlines()[0])
        return end_time

    return None


def validate_checksum(checksum: str, uncompressed_and_decrypted_file_content: bytes) -> bool:
    m = hashlib.md5()
    m.update(uncompressed_and_decrypted_file_content)
    if m.hexdigest() == checksum:
        return True
    else:
        return False
