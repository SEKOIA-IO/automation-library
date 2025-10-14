import base64
import os
import zlib
from unittest.mock import MagicMock

import pytest
import requests_mock
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from imperva import ImpervaModule
from imperva.fetch_logs_v2 import HandlingFileResult, ImpervaLogsConnector
from imperva.helpers import LogFileId


@pytest.fixture
def secret_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())


@pytest.fixture
def secret_key_pem(secret_key):
    return secret_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture
def public_key(secret_key):
    return secret_key.public_key()


@pytest.fixture
def aes_key() -> bytes:
    return os.urandom(16)


@pytest.fixture
def encrypted_aes_key(aes_key, public_key) -> bytes:
    return public_key.encrypt(base64.b64encode(aes_key), padding.PKCS1v15())


def encrypt_with_aes(data: bytes, k) -> bytes:
    iv = 16 * b"\x00"
    # Create cipher object
    cipher = Cipher(algorithms.AES(k), modes.CBC(iv), backend=default_backend())

    # Encrypt the data
    encryptor = cipher.encryptor()

    from cryptography.hazmat.primitives import padding as sym_padding

    padder = sym_padding.PKCS7(128).padder()  # 128 bits = 16 bytes
    padded_data = padder.update(data) + padder.finalize()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    return ciphertext


@pytest.fixture
def trigger(data_storage, secret_key_pem):
    module = ImpervaModule()
    trigger = ImpervaLogsConnector(module=module, data_path=data_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "api_id": "123",
        "api_key": "myapikey",
        "base_url": "https://example.com",
        "keys": {"1": {"private": secret_key_pem}},
    }
    trigger.configuration = {
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def file_1() -> bytes:
    return b"""accountId:1
configId:2
checksum:bd8cc77d12198e36ee2d7536d3161906
format:CEF
startTime:1759413560916
endTime:1759413775485
|==|
EVENT_1
EVENT_2
EVENT_3
"""


def test_fetch_empty_index(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://example.com/logs.index", status_code=200, text="")

        res = trigger.fetch_logs_index()
        assert res == []


def test_fetch_index(trigger):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://example.com/logs.index", status_code=200, text="1_2.log\n1_3.log")

        res = trigger.fetch_logs_index()
        assert res == [LogFileId.from_filename("1_2.log"), LogFileId.from_filename("1_3.log")]


def test_handle_file(trigger, file_1):
    with requests_mock.Mocker() as mock_requests:
        mock_requests.get("https://example.com/logs.index", status_code=200, text="1_1.log")
        mock_requests.get("https://example.com/1_1.log", status_code=200, content=file_1)

        logs = trigger.fetch_logs_index()
        assert len(logs) == 1

        res = trigger.handle_file(logs[0])
        assert res == HandlingFileResult(successful=True, log_name=logs[0], last_timestamp=1759413775485)

        assert trigger.push_events_to_intakes.call_count == 1


def test_decrypt_file_without_encryption(trigger):
    header = b"""accountId:1
configId:2
checksum:bd8cc77d12198e36ee2d7536d3161906
format:CEF
startTime:1759413560916
endTime:1759413775485
|==|\n"""
    true_value = b"event1\nevent2\nevent3"

    non_compressed_and_not_encrypted = header + true_value
    result = trigger.decrypt_file(non_compressed_and_not_encrypted, "1_1.log")
    assert result == true_value

    compressed_only = header + zlib.compress(true_value)
    result = trigger.decrypt_file(compressed_only, "1_1.log")

    assert result == true_value


def test_decrypt_file_with_encryption(trigger, encrypted_aes_key, aes_key, public_key, secret_key):
    content_encrypted_sym_key = base64.b64encode(encrypted_aes_key)
    true_value = b"Event 1: 11232323423\nEvent2: 234234234234\nEvent 3: 23234234243\nEvent2: 234234234234\nEvent 3: 23234234243\nEvent2: 234234234234\nEvent 3: 23234234242\n"

    header = (
        b"""accountId:1
configId:2
checksum:da098edf678c884ea0249eda571b3f57
format:CEF
startTime:1759413560916
endTime:1759413775485
publicKeyId:1
key:"""
        + content_encrypted_sym_key
        + b"\n|==|\n"
    )

    encrypted_content = encrypt_with_aes(true_value, aes_key)
    encrypted_without_compression = header + encrypted_content
    result = trigger.decrypt_file(encrypted_without_compression, "1_1.log")
    assert result.strip() == true_value.strip()
