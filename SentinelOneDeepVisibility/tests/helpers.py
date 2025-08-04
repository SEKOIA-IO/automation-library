import io
from contextlib import asynccontextmanager
from typing import Any, AsyncIterable

import aiofiles


async def async_list(sequence: AsyncIterable) -> list:
    items = []
    async for item in sequence:
        items.append(item)
    return items


@asynccontextmanager
async def async_temporary_file(data, mode="wb+"):
    async with aiofiles.tempfile.NamedTemporaryFile(mode) as f:
        await f.write(data)
        await f.seek(0)

        yield f
