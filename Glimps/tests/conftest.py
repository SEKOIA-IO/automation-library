from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
import hashlib
import io
import pytest
from sekoia_automation import constants
from glimps.submit_file_to_be_analysed_action import WaitForFile
from glimps.models import GLIMPSConfiguration
from glimps.models import GLIMPSModule


@pytest.fixture(scope="session")
def token():
    return "a5555555-b6666666-c7777777-d8888888-e9999999"


@pytest.fixture(scope="session")
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture(scope="session")
def module(token):
    module = GLIMPSModule()
    module.configuration = GLIMPSConfiguration(api_key=token, base_url="https://gmalware.ggp.glimps.re")
    return module


@pytest.fixture(scope="session")
def set_up_wait_for_action(module, symphony_storage):
    return WaitForFile(module=module, data_path=symphony_storage)


@pytest.fixture
def analysis_result():
    uuid = "1da0cb84-c5cc-4832-8882-4a7e9df11ed2"
    mock_analysis_result = {
        "status": True,
        "special_status_code": 0,
        "sha1": "123",
        "done": True,
        "uuid": uuid,
        "sha256": "123",
        "md5": "123",
        "ssdeep": "123",
        "is_malware": True,
        "score": 1000,
        "timestamp": 123,
        "file_count": 1,
        "duration": 20,
        "filetype": "text",
        "size": 4,
    }
    return uuid, mock_analysis_result


@pytest.fixture
def add_file_to_storage(symphony_storage):
    file_name = "eicar.txt"
    file_path: Path = symphony_storage / file_name
    with file_path.open("w+") as f:
        f.write("b" * 4000000)
        f.seek(0)
        hasher = hashlib.sha256()
        while chunk := f.read(io.DEFAULT_BUFFER_SIZE):
            hasher.update(bytes(chunk, "utf-8"))
    return (symphony_storage, file_name, hasher.hexdigest())
