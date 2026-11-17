import asyncio
import os
import time
from concurrent.futures import ProcessPoolExecutor

from docs import N_DOCS, fetch, parse, report

IO_LIMIT = 200                  # samtidige netværkskald
CPU_WORKERS = os.cpu_count()    # én proces pr. kerne
IN_FLIGHT = IO_LIMIT + CPU_WORKERS * 4  # max dokumenter i RAM


async def handle(i, in_flight, io_sem, pool):
    async with in_flight:           # 1) loft over RAM
        async with io_sem:          # 2) loft over I/O
            raw = await fetch(i)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(pool, parse, raw)  # 3) CPU i egen proces


async def main():
    in_flight = asyncio.Semaphore(IN_FLIGHT)
    io_sem = asyncio.Semaphore(IO_LIMIT)

    with ProcessPoolExecutor(CPU_WORKERS) as pool:
        start = time.perf_counter()
        await asyncio.gather(*(handle(i, in_flight, io_sem, pool) for i in range(N_DOCS)))
        report("bounded", start)


if __name__ == "__main__":
    asyncio.run(main())
