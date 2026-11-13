from unittest.mock import Mock

import pytest

from easyvista_modules import EasyVistaModule


@pytest.fixture
def make_action(tmp_path):

    def factory(action_class, **configuration):
        module = EasyVistaModule()
        module.configuration = {
            "base_url": "https://easyvista.example/",
            "tenant_id": "00001",
            "token": "fake-access-token",
            **configuration,
        }
        action = action_class(module=module, data_path=tmp_path)
        action.error = Mock()
        action.log = Mock()
        return action

    return factory


@pytest.fixture
def api_url():
    return "https://easyvista.example/api/v1/00001/requests"
