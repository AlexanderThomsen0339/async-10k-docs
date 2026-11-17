"""
10.000 dokumenter uden at sprænge maskinen.

  I/O  (hente)  -> asyncio + Semaphore     : mange samtidige, billige ventetider
  CPU  (parse)  -> ProcessPoolExecutor     : få samtidige, én pr. kerne
  RAM  (in-flight) -> Semaphore            : loft over hvor mange dokumenter er i hukommelsen

Kør:  python pipeline.py           (adskilt: I/O i loop, CPU i pool)
      python pipeline.py naive     (parse direkte i event loopet)
      python pipeline.py nolimit   (adskilt, men uden lofter -> se RAM eksplodere)
"""
import asyncio
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

try:
    import resource  # kun Unix – bruges til at måle peak RAM
except ImportError:
    resource = None

N_DOCS = 10_000
IO_LIMIT = 200                      # samtidige "netværkskald"
CPU_WORKERS = os.cpu_count() or 1   # én proces pr. kerne
IN_FLIGHT = IO_LIMIT + CPU_WORKERS * 4  # max dokumenter i RAM på én gang

DOC = ("lorem ipsum dolor sit amet " * 2_000).encode()  # ~54 KB pr. dokument


async def fetch(i: int) -> bytes:
    """Simuleret I/O: ventetid, ingen CPU. Erstat med httpx/aiofiles i virkeligheden."""
    await asyncio.sleep(0.05)
    return DOC + b"\n"  # nyt objekt pr. kald, som et rigtigt svar


def parse(raw: bytes) -> int:
    """CPU-arbejde. Skal være en top-level funktion, så den kan pickles til en proces."""
    words = raw.decode().split()
    return sum(len(w) for w in words)  # returnér noget LILLE – resultatet pickles tilbage


async def handle(i, in_flight, io_sem, pool):
    async with in_flight:                 # 1) backpressure: begræns RAM
        async with io_sem:                # 2) begræns samtidige forbindelser
            raw = await fetch(i)
        if pool is None:
            return parse(raw)             # NAIVT: blokerer event loopet
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(pool, parse, raw)  # 3) CPU i separat proces


async def main(mode: str):
    naive = mode == "naive"
    big = 10**9  # "nolimit": reelt ingen lofter
    in_flight = asyncio.Semaphore(big if mode == "nolimit" else IN_FLIGHT)
    io_sem = asyncio.Semaphore(big if mode == "nolimit" else IO_LIMIT)
    pool = None if naive else ProcessPoolExecutor(CPU_WORKERS)

    t0 = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(handle(i, in_flight, io_sem, pool)) for i in range(N_DOCS)]
    total = sum(t.result() for t in tasks)
    dt = time.perf_counter() - t0

    if pool:
        pool.shutdown()
    print(f"{mode:8}: {N_DOCS} docs på {dt:5.2f}s  ({N_DOCS/dt:,.0f} docs/s)  checksum={total}")
    if resource:
        peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB på Linux
        print(f"          peak RAM (hovedproces): {peak_mb:.0f} MB")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "adskilt"))
