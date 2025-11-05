import hashlib
import zlib

from imperva.helpers import LogFileId, extract_last_timestamp, is_compressed, validate_checksum


def test_log_file_id():
    prefix = "1234567890"

    l1 = LogFileId.from_filename("1234567890_1.log")
    l2 = LogFileId.from_filename("1234567890_2.log")
    l3 = LogFileId.from_filename("1234567890_1.log")
    l4 = LogFileId.from_filename("1234567890_4.log")

    assert l1.get_filename() == "1234567890_1.log"
    assert l1 <= l3
    assert l1 >= l3
    assert l1 < l2
    assert l4 > l2
    assert l1 == l3


def test_extract_last_timestamp():
    content = b"""accountId:1
configId:2
checksum:d11ea4ffba2c0c478344905168263cde
format:CEF
startTime:1759915522632
endTime:1759915751990
publicKeyId:1
key:somekey
|==|
abcdefg"""
    assert extract_last_timestamp(content) == 1759915751990


def test_is_compressed():
    assert is_compressed(b"abc") is False

    c = zlib.compressobj().compress(b"abc")
    assert is_compressed(c) is True


def test_validate_checksum():
    md5 = hashlib.md5(b"foo").hexdigest()
    assert validate_checksum(md5, b"foo") is True
    assert validate_checksum(md5, b"bar") is False
