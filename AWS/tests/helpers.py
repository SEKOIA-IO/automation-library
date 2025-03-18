from typing import AsyncIterable


async def async_list(sequence: AsyncIterable) -> list:
    items = []
    async for item in sequence:
        items.append(item)
    return items
