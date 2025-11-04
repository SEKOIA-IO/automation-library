import os
import vt
import hashlib
import time
from typing import Optional, Union, List

class GTIClient:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize GTI client using vt-py."""
        self.api_key = api_key or os.getenv("VT_API_KEY")
        if not self.api_key:
            raise ValueError("API key not provided. Set VT_API_KEY environment variable.")
        self.client = vt.Client(self.api_key)

    # ---------------------
    # Internal helpers
    # ---------------------
    def _safe_request(self, func, *args, **kwargs) -> Optional[Union[vt.Object, List[vt.Object]]]:
        """Wrapper with retry, error handling, NotFound handling."""
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except vt.error.APIError as e:
                if e.code == "NotFoundError":
                    print(f"[Info] Resource not found: {args} — skipping.")
                    return None
                if e.code == "QuotaExceededError":
                    print("[Warn] Quota exceeded, retrying in 5s...")
                    time.sleep(5)
                    continue
                print(f"[Error] VT API error: {e}")
                raise
            except Exception as e:
                print(f"[Error] Unexpected error: {e}, retrying...")
                time.sleep(2)
        raise RuntimeError("Failed after 3 attempts")

    @staticmethod
    def _file_hash(file_path: str) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ---------------------
    # File/URL scanning
    # ---------------------
    def scan_file(self, file_path: str) -> dict:
        """Scan a file, returns existing analysis if already known."""
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError(f"Cannot scan empty file: {file_path}")

        file_hash = self._file_hash(file_path)

        # Check if file already analyzed
        existing = self._safe_request(self.client.get_object, f"/api/v3/files/{file_hash}")
        if existing:
            print(f"[Info] File already analyzed ({file_hash}), returning existing report.")
            return existing.to_dict()

        # Upload and scan new file
        with open(file_path, "rb") as f:
            analysis = self._safe_request(self.client.scan_file, f, wait_for_completion=True)
        return analysis.to_dict() if analysis else {}

    def scan_url(self, url: str) -> dict:
        """Scan a URL."""
        analysis = self._safe_request(self.client.scan_url, url, wait_for_completion=True)
        return analysis.to_dict() if analysis else {}

    # ---------------------
    # IOC / entity operations
    # ---------------------
    def get_ioc_report(self, entity_type: str, entity: str) -> dict:
        """Get IOC report for IP, domain, URL, or file hash."""
        o
