import os
import zipfile

import pytest
from faker import Faker

from utils import files


@pytest.mark.asyncio
async def test_read_zip_line_by_line(logs_content: str, session_faker: Faker):
    file_name = "{0}.log".format(session_faker.word())
    with open(file_name, "w") as file:
        file.write(logs_content)

    zip_file_name = "{0}.zip".format(session_faker.word())
    with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(file_name)

    os.remove(file_name)

    result = []
    async for line in files.read_zip_lines(zip_file_name, buffer_size=10):
        result.append(line)

    assert result == logs_content.split("\n")

    os.remove(zip_file_name)


@pytest.mark.asyncio
async def unzip_zip_file(logs_content: str, session_faker: Faker):
    file_name = "{0}.log".format(session_faker.word())
    with open(file_name, "w") as file:
        file.write(logs_content)

    zip_file_name = "{0}.zip".format(session_faker.word())
    with zipfile.ZipFile(zip_file_name, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(file_name)

    os.remove(file_name)

    directory, files_list = await files.unzip(zip_file_name)

    assert files_list == [file_name]

    with open(file_name, "r") as f:
        result = f.readlines()

    assert result == logs_content.split("\n")

    os.remove(zip_file_name)
    await files.cleanup_resources([directory], files_list)
