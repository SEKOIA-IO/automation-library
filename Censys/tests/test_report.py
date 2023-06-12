import json
import os

import pytest

from censys_module.report import ReportAction


@pytest.fixture
def result():
    return {
        "status": "ok",
        "results": [
            {"key": "United States", "doc_count": 2_083_805},
            {"key": "Japan", "doc_count": 593_265},
            {"key": "China", "doc_count": 488_431},
            {"key": "Germany", "doc_count": 448_079},
            {"key": "United Kingdom", "doc_count": 195_259},
            {"key": "France", "doc_count": 187_713},
            {"key": "Hong Kong", "doc_count": 172_248},
            {"key": "Canada", "doc_count": 134_011},
            {"key": "Netherlands", "doc_count": 108_314},
            {"key": "Ireland", "doc_count": 79890},
            {"key": "Australia", "doc_count": 71164},
            {"key": "Singapore", "doc_count": 68421},
            {"key": "Russia", "doc_count": 60509},
            {"key": "South Korea", "doc_count": 56399},
            {"key": "Brazil", "doc_count": 51457},
            {"key": "Spain", "doc_count": 51295},
            {"key": "Poland", "doc_count": 49926},
            {"key": "Italy", "doc_count": 49668},
            {"key": "Turkey", "doc_count": 47959},
            {"key": "Taiwan", "doc_count": 46845},
            {"key": "India", "doc_count": 46127},
            {"key": "Romania", "doc_count": 45869},
            {"key": "Switzerland", "doc_count": 34066},
            {"key": "Sweden", "doc_count": 32158},
            {"key": "Austria", "doc_count": 28246},
            {"key": "South Africa", "doc_count": 26119},
            {"key": "Czechia", "doc_count": 25785},
            {"key": "Ukraine", "doc_count": 19566},
            {"key": "Belgium", "doc_count": 15942},
            {"key": "Hungary", "doc_count": 14880},
            {"key": "Norway", "doc_count": 13622},
            {"key": "Finland", "doc_count": 13342},
            {"key": "Indonesia", "doc_count": 13154},
            {"key": "Portugal", "doc_count": 11884},
            {"key": "Estonia", "doc_count": 11461},
            {"key": "Thailand", "doc_count": 11317},
            {"key": "Bulgaria", "doc_count": 11266},
            {"key": "Republic of Moldova", "doc_count": 10668},
            {"key": "Denmark", "doc_count": 10607},
            {"key": "Argentina", "doc_count": 9839},
            {"key": "Republic of Lithuania", "doc_count": 9436},
            {"key": "Malaysia", "doc_count": 9122},
            {"key": "Iran", "doc_count": 8748},
            {"key": "Chile", "doc_count": 7249},
            {"key": "Cambodia", "doc_count": 7188},
            {"key": "Mexico", "doc_count": 6807},
            {"key": "Israel", "doc_count": 6259},
            {"key": "New Zealand", "doc_count": 6020},
            {"key": "Vietnam", "doc_count": 5043},
            {"key": "Slovakia", "doc_count": 4812},
            {"key": "Serbia", "doc_count": 4289},
            {"key": "Pakistan", "doc_count": 4088},
            {"key": "Philippines", "doc_count": 3865},
            {"key": "Greece", "doc_count": 3767},
            {"key": "Colombia", "doc_count": 3469},
            {"key": "Slovenia", "doc_count": 3005},
            {"key": "Seychelles", "doc_count": 2751},
            {"key": "Latvia", "doc_count": 2512},
            {"key": "Croatia", "doc_count": 2461},
            {"key": "Albania", "doc_count": 2196},
            {"key": "British Virgin Islands", "doc_count": 1974},
            {"key": "Brunei", "doc_count": 1933},
            {"key": "Cyprus", "doc_count": 1904},
            {"key": "Kazakhstan", "doc_count": 1842},
            {"key": "Luxembourg", "doc_count": 1668},
            {"key": "Bangladesh", "doc_count": 1234},
            {"key": "Uruguay", "doc_count": 1218},
            {"key": "Saudi Arabia", "doc_count": 1199},
            {"key": "United Arab Emirates", "doc_count": 1163},
            {"key": "Peru", "doc_count": 955},
            {"key": "Costa Rica", "doc_count": 851},
            {"key": "Macao", "doc_count": 824},
            {"key": "Ecuador", "doc_count": 805},
            {"key": "Iceland", "doc_count": 799},
            {"key": "Morocco", "doc_count": 788},
            {"key": "Panama", "doc_count": 758},
            {"key": "Puerto Rico", "doc_count": 738},
            {"key": "Belarus", "doc_count": 682},
            {"key": "Tunisia", "doc_count": 666},
            {"key": "Venezuela", "doc_count": 599},
            {"key": "Sri Lanka", "doc_count": 554},
            {"key": "Palestine", "doc_count": 527},
            {"key": "Georgia", "doc_count": 520},
            {"key": "Guatemala", "doc_count": 508},
            {"key": "Egypt", "doc_count": 495},
            {"key": "Kenya", "doc_count": 479},
            {"key": "Nigeria", "doc_count": 439},
            {"key": "Bolivia", "doc_count": 398},
            {"key": "Azerbaijan", "doc_count": 374},
            {"key": "Bosnia and Herzegovina", "doc_count": 353},
            {"key": "Algeria", "doc_count": 345},
            {"key": "Papua New Guinea", "doc_count": 313},
            {"key": "El Salvador", "doc_count": 301},
            {"key": "Mongolia", "doc_count": 299},
            {"key": "Paraguay", "doc_count": 286},
            {"key": "Liechtenstein", "doc_count": 284},
            {"key": "Armenia", "doc_count": 274},
            {"key": "Malta", "doc_count": 264},
            {"key": "Kuwait", "doc_count": 260},
            {"key": "Nepal", "doc_count": 256},
        ],
        "metadata": {
            "count": 5_635_690,
            "backend_time": 266,
            "nonnull_count": 5_591_987,
            "other_result_count": 8195,
            "buckets": 100,
            "error_bound": 0,
            "query": "80.http.get.headers.server: Apache",
        },
    }


@pytest.fixture
def action():
    action = ReportAction()
    action.module.configuration = {"api_user_id": "foo", "api_user_secret": "bar"}
    yield action


def mock_request(censys_mock, arguments, json):
    censys_mock.post(f'https://www.censys.io/api/v1/report/{arguments["index"]}', json=json)


def validate_result(res, expected, storage):
    assert "result_path" in res
    file_path = os.path.join(storage, res["result_path"])
    assert os.path.isfile(file_path)
    with open(file_path) as fp:
        loaded = json.load(fp)
    assert loaded == expected


def test_report(action, symphony_storage, result, censys_mock):
    arguments = {
        "index": "ipv4",
        "query": "80.http.get.headers.server: Apache",
        "field": "location.country",
    }
    mock_request(censys_mock, arguments, result)
    res = action.run(arguments)
    validate_result(res, result, symphony_storage)
