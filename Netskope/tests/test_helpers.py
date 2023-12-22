from netskope_modules.helpers import get_index_name, get_iterator_name, get_tenant_hostname
from netskope_modules.types import NetskopeAlertType, NetskopeEventType


def test_get_iterator_name():
    assert get_iterator_name(NetskopeEventType.APPLICATION, None) == "application"
    assert get_iterator_name(NetskopeEventType.ALERT, NetskopeAlertType.DLP) == "alert-dlp"


def test_get_index_name():
    prefix = "16ab002c51f2"
    base = get_index_name(prefix, NetskopeEventType.ALERT, NetskopeAlertType.MALWARE)

    assert base != get_index_name(prefix, NetskopeEventType.AUDIT, None)
    assert base != get_index_name(prefix, NetskopeEventType.ALERT, NetskopeAlertType.CTEP)
    assert base != get_index_name("75f14f56841e", NetskopeEventType.ALERT, NetskopeAlertType.MALWARE)

    # check consistency
    assert base == get_index_name(prefix, NetskopeEventType.ALERT, NetskopeAlertType.MALWARE)


def test_get_tenant_hostname():
    assert get_tenant_hostname("my.fake.sekoia") == "my.fake.sekoia"
    assert get_tenant_hostname("http://my.fake.sekoia") == "my.fake.sekoia"
    assert get_tenant_hostname("https://my.fake.sekoia") == "my.fake.sekoia"
