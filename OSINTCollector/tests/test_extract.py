import datetime

import pytest
from osintcollector.errors import GZipError, UnzipError
from osintcollector.extract import stix_timestamp, ungzip, unzip


def test_ungzip_error():
    with pytest.raises(GZipError):
        ungzip("foo")


def test_unzip_error():
    with pytest.raises(UnzipError):
        unzip("foo")


def test_stix_timestamp():
    a = stix_timestamp(datetime.datetime(2022, 11, 12, 8, 22, 3, 27))
    assert a == "2022-11-12T08:22:03.000027+00:00"
