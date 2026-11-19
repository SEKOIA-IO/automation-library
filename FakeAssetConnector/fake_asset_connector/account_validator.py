import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from unittest.mock import Mock

from sekoia_automation.account_validator import AccountValidator


class FakeAssetAccountValidator(AccountValidator):
    TIMEOUT = 10

    def fake_request(self) -> None:
        time.sleep(20)

    def validate(self) -> bool:
        self.log("Start validation credentials process", level="info")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.fake_request)
            try:
                future.result(timeout=self.TIMEOUT)
            except TimeoutError:
                self.log(f"Timeout with {self.TIMEOUT} secondes", level="error")
                return False

        self.log("Credentials validated successfully", level="info")
        return True
