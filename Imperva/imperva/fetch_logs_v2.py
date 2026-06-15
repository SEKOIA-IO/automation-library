import base64
import time
import zlib
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import cached_property
from posixpath import join as urljoin

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pydantic.v1 import BaseModel
from sekoia_automation.checkpoint import CheckpointCursor
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration

from . import ImpervaModule
from .client import ApiClient
from .helpers import LogFileId, extract_last_timestamp, is_compressed, validate_checksum
from .metrics import EVENTS_LAG, FORWARD_EVENTS_DURATION, INCOMING_MESSAGES, OUTCOMING_EVENTS


class ImpervaLogsConnectorConfiguration(DefaultConnectorConfiguration):
    frequency: int = 60


class HandlingFileResult(BaseModel):
    log_name: LogFileId
    successful: bool
    last_timestamp: int | None = None

    class Config:
        arbitrary_types_allowed = True


class ImpervaLogsConnector(Connector):
    module: ImpervaModule
    configuration: ImpervaLogsConnectorConfiguration

    NUM_WORKERS = 2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Last known downloaded file id
        self.cursor = CheckpointCursor(path=self.data_path)
        self.last_seen_log = LogFileId.from_filename(self.cursor.offset) if self.cursor.offset else None

        if self.last_seen_log:
            self.log(f"Last seen log is {self.last_seen_log}", level="info")

        self.in_progress: deque[LogFileId] = deque()  # logs that we are downloading right now
        self.processed: deque[LogFileId] = (
            deque()
        )  # all logs that we tried to download and process (both successful and failed)

    @cached_property
    def connector_user_agent(self) -> str:
        return f"sekoiaio-connector-{self.configuration.intake_key}"

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(api_id=self.module.configuration.api_id, api_key=self.module.configuration.api_key)

    def fetch_logs_index(self) -> list[LogFileId]:
        url = urljoin(self.module.configuration.base_url, "logs.index")
        response = self.client.get(url, timeout=60, headers={"User-Agent": self.connector_user_agent})

        if response.ok:
            if response.text == "":
                self.log("Index file is empty", level="info")
                return []

            else:
                return [LogFileId.from_filename(filename) for filename in response.text.split("\n")]

        elif response.status_code == 404:
            self.log("Index file does not yet exist, please allow time for files to be generated.", level="info")

        else:
            response.raise_for_status()

        return []

    def process_file(self, log_name: LogFileId) -> HandlingFileResult:
        result = self.handle_file(log_name)
        self.in_progress.remove(result.log_name)
        self.processed.append(result.log_name)
        return result

    def handle_file(self, log_name: LogFileId) -> HandlingFileResult:
        url = urljoin(self.module.configuration.base_url, log_name.get_filename())
        try:
            response = self.client.get(url, timeout=60, headers={"User-Agent": self.connector_user_agent})
            response.raise_for_status()

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # not found
                self.log(
                    message=f"File {log_name.get_filename()} is not found - probably too old",
                    level="info",
                )
                return HandlingFileResult(log_name=log_name, successful=False)

            raise

        try:
            last_timestamp = extract_last_timestamp(response.content)
            decrypted_file = self.decrypt_file(response.content, log_name.get_filename())
            self.handle_log_decrypted_content(decrypted_file)

            self.log(
                message=f"File {log_name.get_filename()} downloading and processing completed successfully",
                level="info",
            )

        except Exception as e:
            self.log(
                message=f"Fail file decryption or handling : {str(e)}",
                level="error",
            )
            return HandlingFileResult(log_name=log_name, successful=False)

        return HandlingFileResult(log_name=log_name, successful=True, last_timestamp=last_timestamp)

    def handle_log_decrypted_content(self, decrypted_file: bytes) -> None:
        decrypted_file_text: str = decrypted_file.decode("utf-8")  # many lines
        events_list: list[str] = decrypted_file_text.split("\n")

        if events_list[-1] == "":
            del events_list[-1]

        OUTCOMING_EVENTS.labels(intake_key=self.configuration.intake_key).inc(len(events_list))

        self.push_events_to_intakes(events_list)

    def decrypt_file(self, file_content: bytes, filename: str) -> bytes:
        # each log file is built from a header section and a content section, the two are divided by a |==| mark
        file_split_content = file_content.split(b"|==|\n")

        # Formats other than CEF, LEEF, and W3C do not contain headers.
        # These formats also do not require decryption or decompression.
        if len(file_split_content) != 2:
            self.log("File %s is not encrypted/compressed, returning the content as is." % filename, level="info")
            return file_content

        # get the header section content
        file_header_content = file_split_content[0].decode("utf-8")
        # get the log section content
        file_log_content = file_split_content[1]
        # if the file is not encrypted - the "key" value in the file header is '-1'
        file_encryption_key = file_header_content.find("key:")

        if file_encryption_key == -1:
            # uncompress the log content
            if is_compressed(file_log_content):
                uncompressed_and_decrypted_file_content = zlib.decompressobj().decompress(file_log_content)

            else:
                uncompressed_and_decrypted_file_content = file_log_content

        # if the file is encrypted
        else:
            content_encrypted_sym_key = file_header_content.split("key:")[1].splitlines()[0]
            # get the public key id from the log file header
            public_key_id = file_header_content.split("publicKeyId:")[1].splitlines()[0]
            keys = self.module.configuration.keys.get(public_key_id)
            if not keys:
                self.log(
                    message=f"Failed to find a proper certificate for : {filename} "
                    f"who has the publicKeyId of {public_key_id}",
                    level="error",
                )
                raise ValueError("Failed to find a proper certificate")

            # get the checksum
            checksum = file_header_content.split("checksum:")[1].splitlines()[0]

            # get the private key
            private_key = bytes(keys["private"], "utf-8")
            iv = 16 * b"\x00"

            try:
                rsa_private_key = serialization.load_pem_private_key(private_key, password=None)
                content_decrypted_sym_key = rsa_private_key.decrypt(  # type: ignore
                    base64.b64decode(bytes(content_encrypted_sym_key, "utf-8")),
                    padding.PKCS1v15(),
                )

                decryptor = Cipher(
                    algorithms.AES(key=base64.decodebytes(content_decrypted_sym_key)), mode=modes.CBC(iv)
                ).decryptor()
                padded_content = decryptor.update(file_log_content) + decryptor.finalize()

                # remove padding
                unpadder = sym_padding.PKCS7(128).unpadder()
                content = unpadder.update(padded_content) + unpadder.finalize()

                if is_compressed(content):
                    uncompressed_and_decrypted_file_content = zlib.decompressobj().decompress(content)

                else:
                    uncompressed_and_decrypted_file_content = content

                content_is_valid = validate_checksum(checksum, uncompressed_and_decrypted_file_content)
                if not content_is_valid:
                    self.log(
                        message=f"Checksum verification failed for file {filename}",
                        level="error",
                    )
                    raise ValueError("Checksum verification failed")
            except Exception as e:
                self.log(
                    message=f"Error while trying to decrypt the file {filename}: {str(e)}",
                    level="error",
                )
                raise ValueError("Error while trying to decrypt the file" + filename)

        return uncompressed_and_decrypted_file_content

    def run(self) -> None:
        first_run = True
        last_seen_log = self.last_seen_log

        while self.running:
            # save the starting time
            batch_start_time = time.time()

            # download index
            logs_in_index = self.fetch_logs_index()

            if last_seen_log and first_run:
                for log_item in logs_in_index:
                    if log_item in self.in_progress or log_item in self.processed:
                        continue

                    if log_item <= last_seen_log:
                        self.log(
                            "Log %s was before or is %s - ignore it"
                            % (log_item.get_filename(), last_seen_log.get_filename()),
                            level="info",
                        )
                        self.processed.append(log_item)

                first_run = False

            additions: list[LogFileId] = [
                x for x in logs_in_index if x not in self.processed and x not in self.in_progress
            ]
            self.log("%d logs in index file, %d new" % (len(logs_in_index), len(additions)), level="info")
            if len(additions) == 0:
                self.log("No new logs to download", level="info")
                EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(0)

                time.sleep(self.configuration.frequency)
                continue

            INCOMING_MESSAGES.labels(intake_key=self.configuration.intake_key).inc(len(additions))
            self.log("%d new logs to download" % len(additions), level="info")

            self.in_progress.extend(additions)
            last_timestamp = None
            try:
                with ThreadPoolExecutor(max_workers=self.NUM_WORKERS) as pool:
                    for item in pool.map(self.process_file, additions, timeout=3600):
                        if item.last_timestamp is not None and (
                            last_timestamp is None or item.last_timestamp > last_timestamp
                        ):
                            last_timestamp = item.last_timestamp

                if self.processed:
                    if last_timestamp:
                        now = datetime.now(tz=timezone.utc).timestamp()
                        current_lag = now - last_timestamp / 1000.0
                        EVENTS_LAG.labels(intake_key=self.configuration.intake_key).set(current_lag)

                    self.last_seen_log = max(self.processed)
                    self.cursor.offset = self.last_seen_log.get_filename()

                # get the ending time and compute the duration to fetch the events
                batch_end_time = time.time()
                batch_duration = int(batch_end_time - batch_start_time)
                self.log(f"Fetched and forwarded events in {batch_duration} seconds", level="info")
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(batch_duration)
            except Exception as e:
                self.log_exception(e)

                # Clear failed items - successful ones already removed in process_file
                additions_set = set(additions)
                self.in_progress = deque(item for item in self.in_progress if item not in additions_set)

            # compute the remaining sleeping time. If greater than 0, sleep
            delta_sleep = self.configuration.frequency - batch_duration
            if delta_sleep > 0:
                self.log(f"Next batch in the future. Waiting {delta_sleep} seconds", level="info")
                time.sleep(delta_sleep)
