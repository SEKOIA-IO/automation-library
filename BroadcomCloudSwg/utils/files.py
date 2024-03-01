"""Useful utils to work with files."""

import shutil
import zlib
from pathlib import Path, PurePath
from tempfile import mkdtemp
from typing import AsyncGenerator
from zipfile import BadZipFile, ZipFile, is_zipfile
from zlib import MAX_WBITS, decompressobj

import aiofiles
from aiofiles import os as aio_os
from loguru import logger


async def read_zip_lines(file_path: str, buffer_size: int = 64 * 1024) -> AsyncGenerator[str, None]:
    """
    Unzips zipped archive.

    Returns a tuple with temporary dir and list of files.

    Args:
        file_path: str
        buffer_size: int

    Returns:
        tuple[str, list[str]]:
    """
    if is_zipfile(file_path):
        files_info = ZipFile(file_path).infolist()

        logger.info("Zip contains next files: {0}".format(files_info))

        async with aiofiles.open(file_path, mode="rb") as src:
            for zipped_file in files_info:
                file_name = zipped_file.filename
                logger.debug("Unzipping {0}".format(zipped_file))

                seek_offsets: dict[str, int] = {
                    "header": zipped_file.header_offset,
                    "filepath": 30,
                    "filename": len(file_name),
                    "extra": len(zipped_file.extra),
                    "comment": len(zipped_file.comment),
                }

                for _seek_offset in seek_offsets.keys():
                    _seek_offset_value = seek_offsets.get(_seek_offset, 0)
                    await src.read(_seek_offset_value)
                    logger.debug("Done {0} offset read: {1}".format(_seek_offset, _seek_offset_value))

                if zipped_file.is_dir():
                    continue

                decompressor = None
                buffered: bytes = b""

                while True:
                    buffer = await src.read(buffer_size)
                    if decompressor is None:
                        for _bits in [-MAX_WBITS, MAX_WBITS | 16, MAX_WBITS]:
                            try:
                                decompressobj(_bits).decompress(buffer)

                                decompressor = decompressobj(_bits)
                                break
                            except zlib.error:
                                logger.debug("Failed WindowBits: {0}".format(_bits))

                    if not buffer:
                        break

                    if not decompressor:
                        raise ValueError("Failed to initialize decompressor")

                    decompressed_buffer = decompressor.decompress(buffer)

                    decompressed_result = (
                        (buffered + decompressed_buffer if buffered is not None else decompressed_buffer)
                        .decode("utf-8")
                        .split("\n")
                    )

                    if len(decompressed_result) < 1:
                        break

                    buffered = decompressed_result[-1].encode("utf-8")

                    for line in decompressed_result[:-1]:
                        yield line

                flushed: bytes = b""
                if decompressor is not None:
                    flushed = decompressor.flush()

                for line in (buffered + flushed).decode("utf-8").split("\n"):
                    yield line

        return
    raise BadZipFile


async def unzip(file_path: str, directory: str = "/tmp", buffer_size: int = 64 * 1024) -> tuple[str, list[str]]:
    """
    Unzips zipped archive.

    Returns a tuple with temporary dir and list of files.

    Args:
        file_path: str
        directory: str
        buffer_size: int

    Returns:
        tuple[str, list[str]]:
    """
    temp_dir = mkdtemp(dir=directory)
    result_files = []

    if is_zipfile(file_path):
        files_info = ZipFile(file_path).infolist()

        logger.info("Zip contains next files: {0}".format(files_info))

        async with aiofiles.open(file_path, mode="rb") as src:
            for zipped_file in files_info:
                file_name = zipped_file.filename
                result_file_path = Path(str(PurePath(temp_dir, file_name)))
                logger.debug("Unzipping {0} into {1}".format(zipped_file, result_file_path))

                seek_offsets: dict[str, int] = {
                    "header": zipped_file.header_offset,
                    "filepath": 30,
                    "filename": len(file_name),
                    "extra": len(zipped_file.extra),
                    "comment": len(zipped_file.comment),
                }

                for _seek_offset in seek_offsets.keys():
                    _seek_offset_value = seek_offsets.get(_seek_offset, 0)
                    await src.read(_seek_offset_value)
                    logger.debug("Done {0} offset read: {1}".format(_seek_offset, _seek_offset_value))

                if zipped_file.is_dir():
                    result_file_path.mkdir(parents=True, exist_ok=True)
                    continue

                async with aiofiles.open(str(result_file_path), "wb+") as out:
                    decompressor = None

                    while True:
                        buffer = await src.read(buffer_size)
                        if decompressor is None:
                            for _bits in [-MAX_WBITS, MAX_WBITS | 16, MAX_WBITS]:
                                try:
                                    decompressobj(_bits).decompress(buffer)

                                    decompressor = decompressobj(_bits)
                                    break
                                except zlib.error:
                                    logger.debug("Failed WindowBits: {0}".format(_bits))

                        if not buffer:
                            break

                        if not decompressor:
                            raise ValueError("Failed to initialize decompressor")

                        await out.write(decompressor.decompress(buffer))

                    if decompressor is not None:
                        result = decompressor.flush()

                        await out.write(result)

                    result_files.append(str(result_file_path))

        return temp_dir, result_files

    raise BadZipFile


async def cleanup_resources(dirs: list[str] | None = None, files: list[str] | None = None) -> None:
    """
    Cleanup temporary resources.

    Args:
        dirs: list[str] | None
        files: list[str] | None
    """
    if files:
        for file in files:
            try:
                logger.debug("Removing file: {0}".format(file))
                await aio_os.remove(file)
            except FileNotFoundError:
                logger.debug("File not found: {0}".format(file))

    if dirs:
        for directory in dirs:
            logger.debug("Removing directory: {0}".format(directory))
            shutil.rmtree(directory)

    logger.info("All temporary resources have been cleaned up.")
