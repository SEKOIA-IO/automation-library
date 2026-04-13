from ldap3.core.exceptions import LDAPSocketOpenError, LDAPBindError
from microsoft_ad.account_validator import MicrosoftADAccountValidator
import pytest


def test_validates_credentials_when_bind_succeeds():
    validator = object.__new__(MicrosoftADAccountValidator)

    class LdapClient:
        bound = False
        tls_started = True
        result = {}

        def bind(self):
            self.bound = True
            return True

    validator.ldap_client = LdapClient()
    validator.log = lambda **kwargs: None
    validator.error = lambda **kwargs: None
    validator.log_exception = lambda *args, **kwargs: None

    assert validator.validate() is True


def test_returns_false_on_timeout_error():
    validator = object.__new__(MicrosoftADAccountValidator)

    class LdapClient:
        bound = False

        def bind(self):
            raise LDAPSocketOpenError("Timeout occurred !!")

    validator.ldap_client = LdapClient()
    validator.log = lambda **kwargs: None
    validator.error = lambda **kwargs: None
    validator.log_exception = lambda *args, **kwargs: None

    assert validator.validate() is False


def test_returns_false_on_bind_error():
    validator = object.__new__(MicrosoftADAccountValidator)

    class LdapClient:
        bound = False

        def bind(self):
            raise LDAPBindError("LDAP bind failed")

    validator.ldap_client = LdapClient()
    validator.log = lambda **kwargs: None
    validator.error = lambda **kwargs: None
    validator.log_exception = lambda *args, **kwargs: None

    assert validator.validate() is False


def test_returns_false_on_unexpected_exception():
    validator = object.__new__(MicrosoftADAccountValidator)

    class LdapClient:
        bound = False

        def bind(self):
            raise RuntimeError("unexpected")

    validator.ldap_client = LdapClient()
    validator.log = lambda **kwargs: None
    validator.error = lambda **kwargs: None
    validator.log_exception = lambda *args, **kwargs: None

    assert validator.validate() is False


def test_returns_true_when_already_bound():
    """Covers the 'already bound' branch — bind() is not called."""
    validator = object.__new__(MicrosoftADAccountValidator)

    class LdapClient:
        bound = True
        tls_started = True
        result = {}

        def bind(self):
            raise AssertionError("bind() should not be called when already bound")

    validator.ldap_client = LdapClient()
    validator.log = lambda **kwargs: None
    validator.error = lambda **kwargs: None
    validator.log_exception = lambda *args, **kwargs: None

    assert validator.validate() is True
