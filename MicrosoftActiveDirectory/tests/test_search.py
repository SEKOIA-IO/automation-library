from microsoft_ad.actions_base import MicrosoftADModule, MicrosoftADAction
from microsoft_ad.search_actions import SearchAction
from unittest.mock import patch
import pytest
import json
import orjson
import datetime
from ldap3.core.timezone import OffsetTzInfo
from pathlib import Path


def configured_action(action: MicrosoftADAction, data_path: Path | None = None):
    module = MicrosoftADModule()
    a = action(module, data_path=data_path)

    a.module.configuration = {
        "servername": "test_servername",
        "admin_username": "test_admin_username",
        "admin_password": "test_admin_password",
    }

    return a


@pytest.fixture
def one_user_dn():
    return [["CN=integration_test,CN=Users,DC=lab,DC=test,DC=com", 512]]


def test_search_no_attributes():
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    action = configured_action(SearchAction)
    response = True

    with patch(
        "microsoft_ad.search_actions.SearchAction.run",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"search_filter": search, "basedn": basedn})

            assert results is not None


def test_search_with_attributes():
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    attributes = ["name"]

    action = configured_action(SearchAction)
    response = True

    with patch(
        "microsoft_ad.search_actions.SearchAction.run",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run({"search_filter": search, "basedn": basedn, "attributes": attributes})

            assert results is not None


def test_search_in_base_exception():
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    attributes = ["name"]
    action = configured_action(SearchAction)

    # Patch the client property to avoid real LDAP connection
    with patch("microsoft_ad.actions_base.MicrosoftADAction.client") as mock_client:
        mock_client.search.side_effect = Exception("LDAP connection failed")

        with pytest.raises(Exception) as exc_info:
            action.run({"search_filter": search, "basedn": basedn, "attributes": attributes})

        # Verify the exception message
        assert str(exc_info.value) == f"Failed to search in this base {basedn}"


def test_ldap_action_serialization():
    action = configured_action(SearchAction)
    entries = [
        {
            "dn": "CN=John Doe,OU=Users,DC=example,DC=com",
            "attributes": {
                "cn": [b"John Doe"],
                "mail": [b"john.doe@example.com"],
                "date": datetime.datetime(
                    9999,
                    12,
                    31,
                    23,
                    59,
                    59,
                    999999,
                    tzinfo=OffsetTzInfo(offset=0, name="UTC"),
                ),
                "objectGUID": b"\x12\x34\x56\x78\x90",
                "memberOf": [
                    b"CN=Group1,DC=example,DC=com",
                    b"CN=Group2,DC=example,DC=com",
                ],
            },
        },
        {
            "dn": "CN=Jane Smith,OU=Users,DC=example,DC=com",
            "attributes": {
                "cn": [b"Jane Smith"],
                "mail": [b"jane.smith@example.com"],
                "date": datetime.datetime(2024, 11, 21, 15, 16, 38, tzinfo=datetime.timezone.utc),
                "objectGUID": b"\x98\x76\x54\x32\x10",
                "memberOf": [
                    b"CN=Group1,DC=example,DC=com",
                    b"CN=Admins,DC=example,DC=com",
                ],
            },
        },
    ]
    results = action.transform_ldap_results(entries)
    try:
        orjson.dumps(results)
    except (TypeError, ValueError) as e:
        assert False, f"Serialization failed: {str(e)}"


def test_make_serializable_entry_to_json():
    """Covers the entry_to_json branch (line 32)."""
    action = configured_action(SearchAction)

    class FakeLdapEntry:
        def entry_to_json(self):
            return '{"dn": "CN=Test,DC=example,DC=com"}'

    result = action.make_serializable(FakeLdapEntry())
    assert result == '{"dn": "CN=Test,DC=example,DC=com"}'


def test_make_serializable_plain_value():
    """Covers the plain passthrough branch (line 38) — int, None, bool."""
    action = configured_action(SearchAction)

    assert action.make_serializable(42) == 42
    assert action.make_serializable(None) is None
    assert action.make_serializable(True) is True


def test_search_to_file_with_string_result(data_storage):
    """Covers the 'result is str' branch when writing to file (line 64)."""
    action = configured_action(SearchAction, data_path=data_storage)

    with patch("microsoft_ad.search_actions.MicrosoftADAction.client") as mock_client:
        # Make transform_ldap_results return a plain string
        with patch.object(action, "transform_ldap_results", return_value='["raw string result"]'):
            mock_client.search.return_value = None
            mock_client.response = []

            results = action.run(
                {
                    "search_filter": "(cn=test)",
                    "basedn": "dc=example,dc=com",
                    "to_file": True,
                }
            )

    assert "output_path" in results
    output_path = data_storage.joinpath(results["output_path"])
    assert output_path.exists()
    assert output_path.read_text() == '["raw string result"]'


def test_search_to_file_orjson_failure_fallback(data_storage):
    """Covers the orjson failure fallback (lines 68-69) — writes result directly when orjson raises."""
    action = configured_action(SearchAction, data_path=data_storage)

    with patch("microsoft_ad.search_actions.MicrosoftADAction.client") as mock_client:
        # Return a list that orjson can't serialize (e.g. contains a non-serializable object)
        class Unserializable:
            pass

        non_serializable_result = [Unserializable()]
        with patch.object(action, "transform_ldap_results", return_value=non_serializable_result):
            mock_client.search.return_value = None
            mock_client.response = []

            with patch("microsoft_ad.search_actions.orjson.dumps", side_effect=TypeError("not serializable")):
                with pytest.raises(TypeError):
                    # The fallback f.write(result) with a list will raise TypeError from open().write()
                    action.run(
                        {
                            "search_filter": "(cn=test)",
                            "basedn": "dc=example,dc=com",
                            "to_file": True,
                        }
                    )


def test_search_to_file(data_storage):
    username = "Mick Lennon"
    search = f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
    basedn = "dc=example,dc=com"
    attributes = ["name"]

    action = configured_action(SearchAction, data_path=data_storage)
    response = True

    with patch(
        "microsoft_ad.search_actions.SearchAction.run",
        return_value=one_user_dn,
    ):
        with patch("microsoft_ad.search_actions.MicrosoftADAction.client") as mock_client:
            mock_client.modify.return_value = response
            mock_client.result.get.return_value = "success"

            results = action.run(
                {
                    "search_filter": search,
                    "basedn": basedn,
                    "attributes": attributes,
                    "to_file": True,
                }
            )

            assert results is not None
            output_path = data_storage.joinpath(results["output_path"])
            with output_path.open() as fp:
                content = json.load(fp)
                assert content is not None
