import json
import os
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

import pytest
import requests_mock

from detection_rules.trigger_snort_rules import SnortRulesTrigger


@pytest.fixture()
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


@patch.object(SnortRulesTrigger, "send_event")
def test_snort_rules_trigger(send_event_mock, symphony_storage):
    os.environ["CACHE_DIR"] = symphony_storage.as_posix()
    trigger = SnortRulesTrigger(data_path=symphony_storage)
    archives = [
        {
            "url": "https://www.snort.org/rules/snortrules-snapshot-3000.tar.gz",
            "type": "snort",
            "version": "3.0",
            "oinkcode": "apikey",
        }
    ]

    with open("tests/snort3-community-rules.tar.gz", "rb") as mock_fp:
        with requests_mock.mock() as m:
            m.get(archives[0]["url"], content=mock_fp.read())
            m.get(f'{archives[0]["url"]}.md5', text="2ddd1fa1574c6f4dfe8ec9eb17f53115")
            trigger._run(archives)
            assert send_event_mock.call_count == 1

            # Calling it a second time should not send events because there was nothing new
            trigger._run(archives)
            assert send_event_mock.call_count == 1

            bundle_dir = send_event_mock.call_args_list[0][1]["directory"]
            bundle_file = send_event_mock.call_args_list[0][1]["event"]["bundle_path"]

            with symphony_storage.joinpath(bundle_dir).joinpath(bundle_file).open() as fp:
                bundle = json.load(fp)

            assert bundle["type"] == "bundle"
            for item in bundle["objects"]:
                assert item["type"] == "indicator"
                assert item["pattern_type"] == "snort"
                assert item["pattern_version"] == "3.0"
                assert item["pattern"].startswith("alert")
