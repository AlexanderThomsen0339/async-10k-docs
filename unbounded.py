import asyncio
import time
from concurrent.futures import ProcessPoolExecutor

from docs import N_DOCS, fetch, parse, report


async def handle(i, pool):
    raw = await fetch(i)  # intet loft: alle 10.000 hentes med det samme
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(pool, parse, raw)


async def main():
    with ProcessPoolExecutor() as pool:
        start = time.perf_counter()
        await asyncio.gather(*(handle(i, pool) for i in range(N_DOCS)))
        report("unbounded", start)


if __name__ == "__main__":
    asyncio.run(main())
