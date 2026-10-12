import asyncio

shared = []


async def worker(value):
    shared.append(value)


async def run(values):
    await asyncio.gather(worker(1), worker(2))  # expect: AG002
