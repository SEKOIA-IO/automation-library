import asyncio
from datetime import datetime, timedelta

import aiohttp


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
