from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError

from microsoft_ad.account_validator import MicrosoftADAccountValidator


def test_validates_credentials_when_bind_succeeds():
    validator = object.__new__(MicrosoftADAccountValidator)

    class LdapClient:
        bound = False

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
        def bind(self):
            raise RuntimeError("unexpected")

    validator.ldap_client = LdapClient()
    validator.log = lambda **kwargs: None
    validator.error = lambda **kwargs: None
    validator.log_exception = lambda *args, **kwargs: None

    assert validator.validate() is False
