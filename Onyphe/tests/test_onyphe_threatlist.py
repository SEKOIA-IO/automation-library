import pytest
from generic_onyphe_tests import *  # noqa: F401, F403

from onyphe.action_onyphe_threatlist import OnypheThreatlistAction
from onyphe.errors import InvalidArgument


@pytest.fixture
def OnypheAction():
    return OnypheThreatlistAction


@pytest.fixture
def ressource():
    return "threatlist/93.184.216.34"


@pytest.fixture
def bad_ressource():
    return "threatlist/8.8.8"


@pytest.fixture
def arguments():
    return {"ip": "93.184.216.34"}


@pytest.fixture
def bad_arguments():
    return [
        (InvalidArgument, {"ip": "8.8.8"}),
        (InvalidArgument, {"ip": 8}),
        (TypeError, {}),
    ]


threatlist_result = {
    "count": 0,
    "error": 0,
    "max_page": 1,
    "myip": "185.122.161.248",
    "page": 1,
    "results": [],
    "status": "ok",
    "took": "0.187",
    "total": 0,
}


@pytest.fixture
def result():
    return threatlist_result


@pytest.fixture
def result_page_0():
    return threatlist_result


@pytest.fixture
def result_page_1():
    return {}
