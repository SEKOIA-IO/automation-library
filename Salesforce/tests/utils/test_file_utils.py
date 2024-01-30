"""Tests for file utilities."""

import csv
import os

import aiofiles
import pytest
from aiohttp import ClientSession
from aioresponses import aioresponses

from utils.file_utils import csv_file_as_rows, delete_file, save_response_to_temp_file


@pytest.fixture
def random_text(session_faker) -> str:
    """
    Fixture for random text.

    Args:
        session_faker: Faker
    """
    nb_sentences = session_faker.pyint(min_value=2, max_value=10)

    return session_faker.paragraph(nb_sentences=nb_sentences)


@pytest.mark.asyncio
async def test_delete_file(tmp_path, session_faker, random_text):
    """
    Test delete_file.

    Args:
        tmp_path: Path
        session_faker: Faker
        random_text: str
    """
    file_path = os.path.join(tmp_path, session_faker.word())
    with open(file_path, "w+") as file:
        file.write(random_text)

    assert os.path.exists(file_path)

    await delete_file(file_path)

    assert not os.path.exists(file_path)


@pytest.mark.asyncio
async def test_csv_file_content(tmp_path, session_faker, csv_content):
    """
    Test read file content as csv.

    Args:
        tmp_path: Path
        session_faker: Faker
        csv_content: str
    """
    file_path = os.path.join(tmp_path, session_faker.word())
    with open(file_path, "w+") as file:
        file.write(csv_content)

    result = []
    async for row in csv_file_as_rows(file_path):
        result.append(row)

    assert result == list(csv.DictReader(csv_content.splitlines(), delimiter=","))

    await delete_file(file_path)

    assert not os.path.exists(file_path)


@pytest.mark.asyncio
async def test_save_response_to_temporary_file(tmp_path, session_faker):
    """
    Test save response to file.

    Args:
        tmp_path: Path
        session_faker: Faker
    """
    data = session_faker.json(data_columns={"test": ["name", "name", "name"]}, num_rows=1000)
    with aioresponses() as mocked_responses:
        url = session_faker.uri()
        mocked_responses.get(url=url, status=200, body=data, headers={"Content-Length": "{0}".format(len(data))})

        session = ClientSession()
        async with session.get(url) as response:
            file_path = await save_response_to_temp_file(response, temp_dir=str(tmp_path))

    assert os.path.exists(file_path)

    async with aiofiles.open(file_path, encoding="utf-8") as file:
        content = await file.read()

        assert content == data

    await delete_file(file_path)

    assert not os.path.exists(file_path)
