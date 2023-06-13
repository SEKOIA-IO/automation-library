import json
from pathlib import Path
from unittest.mock import Mock, patch

from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
from pytest import fixture

from google_module.big_query import BigQueryAction


@fixture
def action(credentials):
    action = BigQueryAction()
    action.module._configuration = dict(credentials=credentials)
    action._client = Mock()
    yield action


def test_run_simple_query(action: BigQueryAction, symphony_storage: str):
    with patch("google_module.big_query.Client") as client:
        client.return_value.query.return_value = [{}, {}]
        arguments = dict(query="SELECT * FROM `data.mytable`")
        res = action.run(arguments)

    p = Path(symphony_storage).joinpath(res["items_path"])
    assert p.exists()
    loaded = json.loads(p.read_text())
    assert loaded == [{}, {}]


def test_run_get_job_config(action: BigQueryAction):
    arguments = dict(
        query="SELECT * FROM `data.mytable` WHERE foo = @bar",
        parameters=[{"name": "foo", "type": "STRING", "value": "bar"}],
    )
    job_config = action.get_job_config(arguments)
    assert isinstance(job_config, QueryJobConfig)
    assert job_config.query_parameters == [ScalarQueryParameter("foo", "STRING", "bar")]
