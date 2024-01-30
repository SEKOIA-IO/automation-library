"""Contains all useful functions for working with files."""

from typing import Any, AsyncGenerator, Dict

import aiocsv
import aiofiles
from aiofiles import os as aiofiles_os
from aiohttp import ClientResponse
from loguru import logger


async def delete_file(file_name: str) -> None:
    """
    Delete file.

    Args:
        file_name: str
    """
    logger.info("Delete local file {file_name}", file_name=file_name)

    await aiofiles_os.remove(file_name)


async def save_response_to_temp_file(response: ClientResponse, chunk_size: int = 1024, temp_dir: str = "/tmp") -> str:
    """
    Save response to temp file.

    Args:
        response: ClientResponse
        chunk_size: int
        temp_dir: str

    Returns:
        str: path to temp file
    """
    async with aiofiles.tempfile.NamedTemporaryFile("wb", delete=False, dir=temp_dir) as file:
        while True:
            chunk = await response.content.read(chunk_size)
            if not chunk:
                break

            await file.write(chunk)

        file_name: str = file.name

        return file_name


async def csv_file_as_rows(
    file_path: str, encoding: str = "utf-8", delimiter: str = ","
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Read csv file as rows.

    Each row is a dict with keys from the header row.

    Args:
        file_path: str
        encoding: str
        delimiter: str

    Yields:
        dict[str, Any]:
    """
    async with aiofiles.open(file_path, encoding=encoding) as file:
        async for row in aiocsv.AsyncDictReader(file, delimiter=delimiter):
            yield row
