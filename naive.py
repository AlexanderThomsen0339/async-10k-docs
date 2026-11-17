import asyncio
import time

from docs import N_DOCS, fetch, parse, report


async def handle(i, io_sem):
    async with io_sem:
        raw = await fetch(i)
    return parse(raw)  # CPU-arbejde direkte i event loopet: alt andet står stille


async def main():
    io_sem = asyncio.Semaphore(200)
    start = time.perf_counter()
    await asyncio.gather(*(handle(i, io_sem) for i in range(N_DOCS)))
    report("naive", start)


if __name__ == "__main__":
    asyncio.run(main())
