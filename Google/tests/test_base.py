import os

from google_module.base import GoogleAction


class TestAction(GoogleAction):
    __test__ = False

    def run(_: dict):
        pass


def test_set_credentials(credentials: dict):
    action = TestAction()
    action.module._configuration = dict(credentials=credentials)
    action.set_credentials()
    assert os.environ["GOOGLE_APPLICATION_CREDENTIALS"] == str(action.CREDENTIALS_PATH)
    assert action.CREDENTIALS_PATH.exists()
