import os
import time
from datetime import datetime, timedelta, timezone
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from vadecloud_modules import VadeCloudModule
from vadecloud_modules.trigger_vade_cloud_logs import VadeCloudLogsConnector


@pytest.mark.skipif("{'VADE_BASE_URL', 'VADE_LOGIN', 'VADE_PASSWORD'}" ".issubset(os.environ.keys()) == False")
def test_run_integration(symphony_storage):
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    with patch("vadecloud_modules.trigger_vade_cloud_logs.datetime") as mock_datetime:
        mock_datetime.now.return_value = one_hour_ago
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        module = VadeCloudModule()
        trigger = VadeCloudLogsConnector(module=module, data_path=symphony_storage)
        # mock the log function of trigger that requires network access to the api for reporting
        trigger.log = MagicMock()
        trigger.log_exception = MagicMock()
        trigger.push_events_to_intakes = MagicMock()
        trigger.module.configuration = {
            "hostname": os.environ["VADE_BASE_URL"],
            "login": os.environ["VADE_LOGIN"],
            "password": os.environ["VADE_PASSWORD"],
        }
        trigger.configuration = {"intake_key": "0123456789", "ratelimit_per_minute": 2}
        main_thread = Thread(target=trigger.run)
        main_thread.start()

        # wait few seconds
        time.sleep(60)
        trigger._stop_event.set()
        main_thread.join(timeout=60)

        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls) > 0
