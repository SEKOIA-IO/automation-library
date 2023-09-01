# coding: utf-8
# natives
import json
import uuid
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

# third parties
import pytest

# internals
from utils.action_fileutils_readjsonfile import FileUtilsReadJSONFile


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


def test_readjsonfile_without_jsonpath(symphony_storage):
    sample_object = {"a": [{"b": 1, "c": "2"}, "d"]}

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath})

    assert results == {"output": sample_object}


def test_readjsonfile_with_jsonpath_one_match(symphony_storage):
    sample_object = {"a": [{"b": 1, "c": "2"}, "d"]}

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "jsonpath": "$.a[0].b"})

    assert results == {"output": sample_object["a"][0]["b"]}


def test_readjsonfile_with_jsonpath_one_match_return_list(symphony_storage):
    sample_object = {"a": [{"b": 1, "c": "2"}, "d"]}

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "jsonpath": "$.a[0].b", "return_list": True})

    assert results == {"output": [sample_object["a"][0]["b"]]}


def test_readjsonfile_with_jsonpath_multiple_match(symphony_storage):
    sample_object = {"a": [{"b": 1, "c": "2"}, "d", {"b": 3}]}

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "jsonpath": "$.a[*].b"})

    assert results == {"output": [1, 3]}


def test_readjsonfile_with_jsonpath_no_match(symphony_storage):
    sample_object = {"a": [{"b": 1, "c": "2"}, "d", {"b": 3}]}

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "jsonpath": "$.b"})

    assert results == {"output": None}


def test_readjsonfile_with_jsonpath_one_match_to_file(symphony_storage):
    sample_object = {"a": [{"b": 1, "c": "2"}, "d"]}

    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "jsonpath": "$.a[0].b", "to_file": True})

    output_path = symphony_storage / results["output_path"]
    with output_path.open() as fp:
        assert json.load(fp) == sample_object["a"][0]["b"]


def test_read_json_file_string_match_to_file(symphony_storage):
    sample_object = {"a": [{"b": "mymatch", "c": "2"}, "d"]}
    _test_read_json_file_match_to_file(symphony_storage, sample_object, is_json=False)


def test_read_json_file_int_match_to_file(symphony_storage):
    sample_object = {"a": [{"b": 42, "c": "2"}, "d"]}
    _test_read_json_file_match_to_file(symphony_storage, sample_object)


def test_read_json_file_dict_match_to_file(symphony_storage):
    sample_object = {"a": [{"b": {"foo": "bar"}, "c": "2"}, "d"]}
    _test_read_json_file_match_to_file(symphony_storage, sample_object)


def _test_read_json_file_match_to_file(symphony_storage, sample_object, is_json=True):
    filepath = symphony_storage / str(uuid.uuid4())

    with filepath.open("w") as fd:
        json.dump(sample_object, fd)

    action = FileUtilsReadJSONFile(data_path=symphony_storage)
    results = action.run({"file_path": filepath, "jsonpath": "$.a[0].b", "to_file": True})

    output_path = symphony_storage / results["output_path"]
    with output_path.open() as fp:
        content = fp.read() if not is_json else json.load(fp)
        assert content == sample_object["a"][0]["b"]
