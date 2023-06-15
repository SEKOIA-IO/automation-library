import hashlib
import tarfile
from pathlib import Path
from zipfile import ZipFile

import requests


class RuleArchive:
    """
    Class representing a rule archive.

    The rule archive is initially stored remotely.
    A remote md5 file is also available to check if the archive has changed.
    """

    _md5: str | None

    def __init__(self, url: str, oinkcode: str | None = None, temp_dir: str = "/tmp"):
        self.url = url
        self._oinkcode = oinkcode
        self._temp_dir = Path(temp_dir)
        self._downloaded = False
        self._md5 = None

    @property
    def file_name(self) -> str:
        """
        Extract the file name from the url
        """
        return Path(self.url).name.split("?", 1)[0]

    @property
    def remote_md5(self) -> str:
        """
        Fetch the remote md5 value
        """
        if self._md5:
            return self._md5
        url = f"{self.url}.md5"
        result: str = self._get(url).text.strip()
        self._md5 = result
        return result

    @property
    def tmp_file_path(self) -> Path:
        """
        Generate the temporary file path
        """
        url_hash = hashlib.md5(self.url.encode("utf-8")).hexdigest()
        return self._temp_dir.joinpath(f"{url_hash}-{self.file_name}")

    def download(self):
        """
        Download the archive file and store it at tmp_file_path
        """
        result = self._get(self.url, stream=True)
        with self.tmp_file_path.open("wb") as tmp:
            for line in result.iter_content(512):
                tmp.write(line)
        self._downloaded = True

    def remove(self):
        """
        Remove tmp_file_path if it exists
        """
        if self.tmp_file_path.exists():
            self.tmp_file_path.unlink()

    def extract_files(self) -> dict:
        """
        Extract the archive and store the files in memory.
        """
        files = self._extract()
        if files:
            return files

        # The file is not an archive, treat it as an individual file.
        basename = self.tmp_file_path.name.split("-", 1)[1]
        return {basename: self.tmp_file_path.open("rb").read()}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.remove()

    def _get(self, url, **kwargs):
        if self._oinkcode:
            url = f"{url}?oinkcode={self._oinkcode}"
        result = requests.get(url, **kwargs)
        result.raise_for_status()
        return result

    def _extract_tar(self) -> dict:
        files = {}
        with tarfile.open(self.tmp_file_path.resolve(), mode="r:*") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                file_obj = tf.extractfile(member)
                if file_obj:
                    files[member.name] = file_obj.read()

        return files

    def _extract_zip(self) -> dict:
        files = {}
        with ZipFile(self.tmp_file_path.resolve()) as reader:
            for name in reader.namelist():
                if name.endswith("/"):
                    continue
                files[name] = reader.read(name)

        return files

    def _extract(self) -> dict | None:
        if ".tar" in self.tmp_file_path.suffixes:
            return self._extract_tar()

        if self.tmp_file_path.suffix == ".zip":
            return self._extract_zip()

        return None
