import asyncio
import gzip
import json
from collections.abc import AsyncGenerator, Generator, Iterable
from io import BytesIO
from itertools import islice
from typing import Any

import aiohttp
import requests


class AsyncGeneratorConverter:
    def __init__(self, async_generator: AsyncGenerator, loop: asyncio.AbstractEventLoop):
        self.async_iterator = aiter(async_generator)
        self.loop = loop

    def __iter__(self):
        return self

    async def get_anext(self) -> Any:
        return await anext(self.async_iterator)

    def __next__(self):
        try:
            return self.loop.run_until_complete(self.get_anext())
        except StopAsyncIteration as e:
            raise StopIteration from e


async def gather_with_concurrency(n: int, *tasks):
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*(sem_task(task) for task in tasks))


async def async_fetch_content(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()


def __fetch_content(batch_url: str) -> list[dict]:
    response = requests.get(batch_url, timeout=60)
    response.raise_for_status()

    file_content = BytesIO(response.content)

    result = []
    with gzip.open(file_content, "rt") as file:
        for line in file:
            result.append(json.loads(line))

    return result


def sync_download_batch(urls: list[str]) -> list[dict]:
    result = []
    for url in urls:
        result.extend(__fetch_content(url))

    return result


async def async_download_batch(urls: list[str]) -> list[dict]:
    tasks = []
    for url in urls:
        tasks.append(asyncio.ensure_future(async_fetch_content(url)))

    num_concurrency = 8
    items = await gather_with_concurrency(num_concurrency, *tasks)

    result = []
    for item in items:
        file_content = BytesIO(item)
        with gzip.open(file_content, "rt") as file:
            for line in file:
                result.append(json.loads(line))

    return result


def download_batches(urls: list[str], use_async=True) -> list[dict]:
    if use_async:
        return asyncio.run(async_download_batch(urls))

    else:
        return sync_download_batch(urls)


def batched(iterable: Iterable, n: int) -> Generator[list, None, None]:
    """
    Yield batches of n items from iterable
    """
    if n < 1:
        raise ValueError("n must be at least one")

    iterator = iter(iterable)
    while batch := list(islice(iterator, n)):
        yield batch
