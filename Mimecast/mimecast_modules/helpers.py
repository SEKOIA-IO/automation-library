import asyncio
import gzip
import json
from datetime import datetime, timedelta
from io import BytesIO
from typing import Callable, Sequence

import aiohttp
import requests
from cachetools import Cache


def get_upper_second(time: datetime) -> datetime:
    """
    Return the upper second from a datetime

    :param datetime time: The starting datetime
    :return: The upper second of the starting datetime
    :rtype: datetime
    """
    return (time + timedelta(seconds=1)).replace(microsecond=0)


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


def filter_collected_events(events: Sequence, getter: Callable, cache: Cache) -> list:
    """
    Filter events that have already been filter_collected_events

    Args:
        events: The list of events to filter
        getter: The callable to get the criteria to filter the events
        cache: The cache that hold the list of collected events
    """

    selected_events = []
    for event in events:
        key = getter(event)

        # If the event was already collected, discard it
        if key is None or key in cache:
            continue

        cache[key] = True
        selected_events.append(event)

    return selected_events
