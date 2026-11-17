import asyncio
import re
import time
from collections import Counter

N_DOCS = 10_000
DOC = ("lorem ipsum dolor sit amet " * 2_000).encode()  # ca. 54 KB


async def fetch(i):
    await asyncio.sleep(0.05)  # simuleret netværk: ventetid, ingen CPU
    return DOC + b"\n"         # nyt objekt pr. kald, som et rigtigt svar


def parse(raw):
    words = re.findall(r"\w+", raw.decode().lower())  # CPU-arbejde: ca. 2 ms
    return Counter(words).most_common(3)               # returnér noget lille


def report(name, start):
    seconds = time.perf_counter() - start
    print(f"{name}: {N_DOCS} docs på {seconds:.2f}s ({N_DOCS / seconds:,.0f} docs/s)")
    try:
        import resource
        print(f"peak RAM: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB")  # KB på Linux
    except ImportError:
        pass  # findes ikke på Windows
