import asyncio
import io
from concurrent.futures import Executor
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, AsyncIterable

import aiofiles
from aiofiles.threadpool.binary import AsyncBufferedReader


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


async def async_bytesIO(
    data: bytes,
    *,
    loop: asyncio.AbstractEventLoop | None = None,
    executor: Executor | None = None,
) -> Any:
    if loop is None:
        loop = asyncio.get_running_loop()

    cb = partial(
        io.BytesIO,
        data,
    )
    f = await loop.run_in_executor(executor, cb)
    return AsyncBufferedReader(f, loop=loop, executor=executor)
