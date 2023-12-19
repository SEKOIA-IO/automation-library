import base64
import hashlib
import os
import re
import time
import traceback
import zlib
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any
from posixpath import join as urljoin

import requests
import urllib3
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests import Response
from sekoia_automation.constants import CHUNK_BYTES_MAX_SIZE, EVENT_BYTES_MAX_SIZE
from sekoia_automation.trigger import Trigger
from tenacity import Retrying, stop_after_attempt, wait_exponential


class HTTPError(Exception):
    pass


class LogsDownloader(Trigger):
    config: Any
    file_downloader: Any
    last_known_downloaded_file_id: Any
    logs_file_index: Any
    retries: int = 0

    testing: bool = False  # used to bypass sleeps during tests

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def initializing(self):
        self.config: Config = Config(
            API_ID=self.module.configuration["api_id"],
            API_KEY=self.module.configuration["api_key"],
            BASE_URL=self.module.configuration["base_url"],
        )

        self.log(message="Initializing LogsDownloader", level="debug")

        self.file_downloader = FileDownloader(self.config, self.log)
        self.last_known_downloaded_file_id = LastFileId()
        self.logs_file_index = LogsFileIndex(self.config, self.log, self.file_downloader)
        self.chunk_size = self.configuration.get("chunk_size", 500)

        self.log(message="LogsDownloader initializing is done", level="info")

    def run(self) -> None:
        self.initializing()

        while True:
            self.get_log_files()

    def get_log_files(self):
        """
        Download the log files.
        If this is the first time, we get the logs.index file, scan it, and download all the files in it.
        It this is not the first time, we try to fetch the next log file.
        """
        last_log_id: str | None = self.last_known_downloaded_file_id.get_last_log_id()

        if last_log_id == "":
            return self._get_log_files_first_run()
        return self._get_log_files(last_log_id)

    def _get_log_files_first_run(self):
        self.log(
            message="No last downloaded file is found - downloading index file and starting to download all "
            "the log files in it",
            level="info",
        )
        try:
            self.logs_file_index.download()
            self.first_time_scan()
        except Exception as e:
            self.log(
                message=f"Failed to downloading index file and starting to download all the log files in it "
                f"- {str(e)}, {traceback.format_exc()}",
                level="error",
            )
            self.log(
                message="Sleeping for 30 seconds before trying to fetch logs again...",
                level="info",
            )
            if not self.testing:
                time.sleep(30)

    def _get_log_files(self, last_log_id: str):
        self.log(
            message=f"The last known downloaded file is {last_log_id}",
            level="debug",
        )
        next_file: str = self.last_known_downloaded_file_id.get_next_file_name()
        self.log(message=f"Will now try to download {next_file}", level="debug")

        try:
            success: bool = self.handle_file(next_file)

            if success:
                self.log(
                    message=f"Successfully handled file {next_file}, updating the last known downloaded file id",
                    level="debug",
                )

                self.log(
                    message=f"Sleeping for {self.configuration.get('frequency', 2)} seconds before fetching the "
                    f"next logs file",
                    level="info",
                )
                self.retries = 0
                if not self.testing:
                    time.sleep(self.configuration.get("frequency", 2))

                self.last_known_downloaded_file_id.move_to_next_file()

            else:
                self.log(
                    message=f"Could not get log file {next_file}. "
                    f"It could be that the log file does not exist yet.",
                    level="info",
                )
                if self.retries >= 10:
                    self.log(
                        message="Failed to download file 10 times, trying to recover.",
                        level="info",
                    )
                    self.recovering_after_too_much_retries(next_file)
                else:
                    self.log(
                        message="Sleeping for 30 seconds before trying to fetch logs again...",
                        level="info",
                    )
                    self.retries += 1
                    if not self.testing:
                        time.sleep(30)

        except Exception as e:
            self.log(
                message=f"Failed to download file {next_file}. "
                f"Error is - {str(e)} , {str(traceback.format_exc())}",
                level="error",
            )

    def recovering_after_too_much_retries(self, next_file: str) -> None:
        self.logs_file_index.download()
        logs_in_index = self.logs_file_index.indexed_logs()
        log_id: int = self.get_counter_from_file_name(next_file)
        first_log_id_in_index: int = self.get_counter_from_file_name(logs_in_index[0])

        if log_id < first_log_id_in_index:
            self.log(
                message="Current downloaded file is not in the index file any more. This is "
                "probably due to a long delay in downloading. Attempting to recover"
            )
            self.last_known_downloaded_file_id.remove_last_log_id()

        elif self.last_known_downloaded_file_id.get_next_file_name(skip_files=1) in logs_in_index:
            self.log(message="Skipping " + str(next_file), level="warning")
            self.last_known_downloaded_file_id.move_to_next_file()

        else:
            self.log(
                message="Next file still does not exist. Sleeping for 30 seconds and continuing normally",
                level="info",
            )
            self.retries = 0
            if not self.testing:
                time.sleep(30)

    def first_time_scan(self):
        """Scan the logs.index file, and download all the log files in it"""
        self.log(
            message="No last index found, will now scan the entire index...",
            level="info",
        )
        # get the list of file names from the index file
        logs_in_index = self.logs_file_index.indexed_logs()

        for log_file_name in logs_in_index:
            if LogsFileIndex.validate_log_file_format(str(log_file_name.rstrip("\r\n"))):
                success = self.handle_file(log_file_name)

                if success:
                    # set the last handled log file information
                    self.last_known_downloaded_file_id.update_last_log_id(log_file_name)
                else:
                    # skip the file and try to get the next one
                    self.log(message=f"Skipping File {log_file_name}", level="warning")
        self.log(
            message="Completed fetching all the files from the logs files index file",
            level="info",
        )

    def handle_file(self, logfile, wait_time=5) -> bool:
        """Download a log file, decrypt, unzip, and store it"""
        # we will try to get the file a max of 3 tries
        counter = 0
        while counter <= 3:
            result = self.download_log_file(logfile)

            if result[0] == "OK":
                try:
                    decrypted_file = self.decrypt_file(result[1], logfile)
                    self.handle_log_decrypted_content(decrypted_file)

                    self.log(
                        message=f"File {logfile} download and processing completed successfully",
                        level="info",
                    )
                    return True

                except Exception as e:
                    self.log(
                        message=f"Fail file decryption or handling : {str(e)}",
                        level="error",
                    )
                    break

            # if the file is not found (could be that it is not generated yet)
            elif result[0] == "NOT_FOUND" or result[0] == "ERROR":
                counter += 1

            if wait_time > 0 and counter <= 3:
                self.log(
                    message=f"Sleeping for {wait_time} seconds until next file download retry number "
                    f"{counter} out of 3",
                    level="info",
                )
                if not self.testing:
                    time.sleep(wait_time)
            # if the downloader was stopped
            else:
                return False
        # if we didn't succeed to download the file
        return False

    def _chunk_events(self, events: Sequence) -> Generator[list[Any], None, None]:
        """Group events by chunk.

        :param sequence events: The events to group
        """
        chunk: list[Any] = []
        chunk_bytes: int = 0
        nb_discarded_events: int = 0

        # iter over the events
        for event in events:
            if len(event) > EVENT_BYTES_MAX_SIZE:
                nb_discarded_events += 1
                continue

            # if the chunk is full
            if chunk_bytes + len(event) > CHUNK_BYTES_MAX_SIZE:
                # yield the current chunk and create a new one
                yield chunk
                chunk = []
                chunk_bytes = 0

            # add the event to the current chunk
            chunk.append(event)
            chunk_bytes += len(event)

        # if the last chunk is not empty
        if len(chunk) > 0:
            # yield the last chunk
            yield chunk

        # if events were discarded, log it
        if nb_discarded_events > 0:
            self.log(message=f"{nb_discarded_events} too long events " "were discarded (length > 64kb)")

    def _retry(self):
        return Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    @cached_property
    def __connector_user_agent(self):
        return f"sekoiaio-connector-{self.configuration['intake_key']}"

    def push_events_to_intakes(self, events: list[str]) -> list:
        # no event to push
        if not events:
            return []

        # Reset the consecutive error count
        self._error_count = 0
        self._last_events_time = datetime.utcnow()
        intake_host = os.environ.get("SEKOIAIO_INTAKE_HOST", "https://intake.sekoia.io")
        batch_api = urljoin(intake_host, "batch")

        # Collect event_ids
        event_ids: list = []

        # forward the events
        for chunk in self._chunk_events(events):
            try:
                request_body = {
                    "intake_key": self.configuration["intake_key"],
                    "jsons": chunk,
                }

                for attempt in self._retry():
                    with attempt:
                        res: Response = requests.post(
                            batch_api,
                            json=request_body,
                            headers={"User-Agent": self.__connector_user_agent},
                            timeout=30,
                        )
                if res.status_code > 299:
                    self.log(f"Intake rejected events: {res.text}", level="error")
                    res.raise_for_status()
                event_ids.extend(res.json().get("event_ids", []))
            except Exception as ex:
                self.log_exception(ex, message=f"Failed to forward {len(chunk)} events")

        return event_ids

    def handle_log_decrypted_content(self, decrypted_file):
        decrypted_file = decrypted_file.decode("utf-8")  # many lines
        events_list: list[str] = decrypted_file.split("\n")

        if events_list[-1] == "":
            del events_list[-1]

        self.push_events_to_intakes(events=events_list)

    def decrypt_file(self, file_content, filename):
        """Decrypt a file content"""
        # each log file is built from a header section and a content section, the two are divided by a |==| mark
        file_split_content = file_content.split(b"|==|\n")
        # get the header section content
        file_header_content = file_split_content[0].decode("utf-8")
        # get the log section content
        file_log_content = file_split_content[1]
        # if the file is not encrypted - the "key" value in the file header is '-1'
        file_encryption_key = file_header_content.find("key:")

        if file_encryption_key == -1:
            uncompressed_and_decrypted_file_content = zlib.decompressobj().decompress(file_log_content)

        else:
            content_encrypted_sym_key = file_header_content.split("key:")[1].splitlines()[0]

            # get the public key id from the log file header
            public_key_id = file_header_content.split("publicKeyId:")[1].splitlines()[0]

            keys = self.configuration["keys"].get(public_key_id)

            if not keys:
                self.log(
                    message=f"Failed to find a proper certificate for : {filename} "
                    f"who has the publicKeyId of {public_key_id}",
                    level="error",
                )
                raise ValueError("Failed to find a proper certificate")

            checksum = file_header_content.split("checksum:")[1].splitlines()[0]

            private_key = bytes(keys["private"], "utf-8")
            iv = os.urandom(16)

            try:
                rsa_private_key = serialization.load_pem_private_key(private_key, password=None)
                content_decrypted_sym_key = rsa_private_key.decrypt(
                    base64.b64decode(bytes(content_encrypted_sym_key, "utf-8")),
                    padding.PKCS1v15(),
                )

                decryptor = Cipher(algorithms.AES(key=content_decrypted_sym_key), mode=modes.CBC(iv)).decryptor()
                uncompressed_and_decrypted_file_content = zlib.decompressobj().decompress(
                    decryptor.update(file_log_content) + decryptor.finalize()
                )
                content_is_valid = self.validate_checksum(checksum, uncompressed_and_decrypted_file_content)
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

    def download_log_file(self, filename: str):
        filename = str(filename.rstrip("\r\n"))
        try:
            file_content = self.file_downloader.request_file_content(self.config.BASE_URL + filename)
            if file_content != "":
                return "OK", file_content
            else:
                return "NOT_FOUND", file_content
        except Exception:
            self.log(message="Error while trying to download file", level="error")
            return "ERROR"

    @staticmethod
    def validate_checksum(checksum, uncompressed_and_decrypted_file_content):
        m = hashlib.md5()
        m.update(uncompressed_and_decrypted_file_content)
        if m.hexdigest() == checksum:
            return True
        else:
            return False

    def get_counter_from_file_name(self, file_name: str) -> int:
        """Gets the next log file name that we should download"""
        curr_log_file_name_arr = file_name.split("_")
        return int(curr_log_file_name_arr[1].rstrip(".log"))


class LastFileId:
    """A class for managing the last known successfully downloaded log file"""

    last_id: str | None = ""

    def get_last_log_id(self) -> str | None:
        """Gets the last known successfully downloaded log file id"""
        return self.last_id

    def update_last_log_id(self, last_id: str) -> None:
        """Update the last known successfully downloaded log file id"""
        self.last_id = last_id

    def remove_last_log_id(self) -> None:
        """Remove the LastKnownDownloadedFileId.txt file. Used to skip missing files."""
        self.last_id = ""

    def get_next_file_name(self, skip_files=0) -> str:
        """Gets the next log file name that we should download"""
        if not self.last_id:
            raise ValueError()
        curr_log_file_name_arr = self.last_id.split("_")
        curr_log_file_id = int(curr_log_file_name_arr[1].rstrip(".log")) + 1 + skip_files
        new_log_file_id = curr_log_file_name_arr[0] + "_" + str(curr_log_file_id) + ".log"
        return new_log_file_id

    def move_to_next_file(self):
        """Increment the last known successfully downloaded log file id"""
        self.update_last_log_id(self.get_next_file_name())


class LogsFileIndex:
    """LogsFileIndex - A class for managing the logs files index file"""

    def __init__(self, config, logger, downloader):
        self.config: Config = config
        self.content: list[str] | None = None
        self.hash_content: set[str] | None = None
        self.logger = logger
        self.file_downloader: FileDownloader = downloader

    def indexed_logs(self) -> list[str] | None:
        """Gets the indexed log files"""
        return self.content

    def download(self):
        """Downloads a logs file index file"""
        self.logger(message="Downloading logs index file...", level="info")

        file_content = self.file_downloader.request_file_content(self.config.BASE_URL + "logs.index")

        if file_content != "":
            content = file_content.decode("utf-8")

            if LogsFileIndex.validate_logs_index_file_format(content):
                self.content = content.splitlines()
                self.hash_content = set(self.content)
            else:
                self.logger(message="log.index, Pattern Validation Failed", level="error")
                raise ValueError("log.index, Pattern Validation Failed")
        else:
            raise ValueError("Index file does not yet exist, please allow time for files to be generated.")

    @staticmethod
    def validate_logs_index_file_format(content: str) -> bool:
        """Validates that format name of the logs files inside the logs index file"""
        file_rex = re.compile("(\\d+_\\d+\\.log\n)+")
        if file_rex.match(content):
            return True
        return False

    @staticmethod
    def validate_log_file_format(content: str) -> bool:
        """Validates a log file name format"""
        file_rex = re.compile(r"(\d+_\d+\.log)")
        if file_rex.match(content):
            return True
        return False


@dataclass
class Config:
    API_ID: str
    API_KEY: str
    BASE_URL: str
    PROCESS_DIR: str | None = None
    SAVE_LOCALLY: str | None = None
    USE_PROXY: str | None = None
    PROXY_SERVER: str | None = None
    USE_CUSTOM_CA_FILE: str | None = None
    CUSTOM_CA_FILE: str | None = None


class FileDownloader:
    """FileDownloader - A class for downloading files"""

    def __init__(self, config: Config, logger):
        self.config: Config = config
        self.logger = logger

    def request_file_content(self, url: str, timeout: int = 20):
        """A method for getting a destination URL file content"""
        response_content = b""
        https: urllib3.ProxyManager | urllib3.PoolManager
        if self.config.USE_PROXY == "YES" and self.config.USE_CUSTOM_CA_FILE == "YES" and self.config.PROXY_SERVER:
            self.logger(message="Using proxy %s" % self.config.PROXY_SERVER, level="info")
            https = urllib3.ProxyManager(
                self.config.PROXY_SERVER,
                ca_certs=self.config.CUSTOM_CA_FILE,
                cert_reqs="CERT_REQUIRED",
                timeout=timeout,
            )
        elif self.config.USE_PROXY == "YES" and self.config.USE_CUSTOM_CA_FILE == "NO" and self.config.PROXY_SERVER:
            self.logger(message="Using proxy %s" % self.config.PROXY_SERVER, level="info")
            https = urllib3.ProxyManager(self.config.PROXY_SERVER, cert_reqs="CERT_REQUIRED", timeout=timeout)
        elif self.config.USE_PROXY == "NO" and self.config.USE_CUSTOM_CA_FILE == "YES":
            https = urllib3.PoolManager(
                ca_certs=self.config.CUSTOM_CA_FILE,
                cert_reqs="CERT_REQUIRED",
                timeout=timeout,
            )
        else:  # no proxy and no custom CA file
            https = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", timeout=timeout)

        try:
            auth_header = urllib3.make_headers(basic_auth=f"{self.config.API_ID}:{self.config.API_KEY}")
            response = https.request("GET", url, headers=auth_header)

            if response.status == 200:
                self.logger(message=f"Successfully downloaded file from URL {url}", level="info")
                response_content = response.data

            elif response.status == 404:
                self.logger(
                    message=f"Could not find file {url}. Response code is {response.status}",
                    level="warning",
                )
                return response_content
            elif response.status == 401:
                self.logger(
                    message=f"Authorization error - Failed to download file {url}. Response code is {response.status}",
                    level="error",
                )
                raise HTTPError("Authorization error")
            elif response.status == 429:
                self.logger(
                    message=f"Rate limit exceeded - Failed to download file {url}. Response code is {response.status}",
                    level="error",
                )
                raise HTTPError("Rate limit error")
            else:
                self.logger(
                    message=f"Failed to download file {url}. Response code is {response.status}. "
                    f"Data is {response.data.decode()}",
                    level="error",
                )

            response.close()

            return response_content

        except urllib3.exceptions.HTTPError as e:
            self.logger(
                message=f"An error has occur while making a open connection to {url}. {e}",
                level="error",
            )
            raise HTTPError("Connection error")

        except Exception:
            self.logger(
                message=f"An error has occur while making a open connection to {url}. {str(traceback.format_exc())}",
                level="error",
            )
            raise HTTPError("Connection error")
