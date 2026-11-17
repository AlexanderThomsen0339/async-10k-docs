# 10.000 dokumenter uden at sprænge maskinen

Et minimalt eksempel i Python på, hvordan man behandler mange dokumenter hurtigt **og** med styr på hukommelsen:

- **`asyncio` + `Semaphore`** til I/O (hente dokumenter)
- **`ProcessPoolExecutor`** til CPU (parse dokumenter)
- **og hvorfor de to skal holdes adskilt**

Kun standardbiblioteket. Ét script på ca. 70 linjer. Kræver Python 3.11+ (bruger `asyncio.TaskGroup`).

```bash
python pipeline.py           # adskilt: I/O i event loop, CPU i process pool
python pipeline.py naive     # parse direkte i event loopet
python pipeline.py nolimit   # adskilt, men uden lofter
```

## Idéen

Der er tre forskellige knappe ressourcer. Hver får sit eget værktøj og sit eget loft.

| Ressource | Værktøj | Loft | Hvorfor |
|---|---|---|---|
| Ventetid (netværk/disk) | `asyncio` + `Semaphore(200)` | Højt | Det koster næsten intet at vente. Hundredvis af kald kan være i gang på én tråd |
| CPU (parsing) | `ProcessPoolExecutor` | Én proces pr. kerne | GIL'en gør, at én Python-proces kun bruger én kerne. Flere processer end kerner giver bare overhead |
| RAM | `Semaphore(IN_FLIGHT)` | Lidt over hvad pipelinen kan nå | Backpressure: hentning må ikke løbe fra parsing |

```
             in_flight (RAM-loft)
  ┌───────────────────────────────────────────┐
  │   io_sem (200)            process pool    │
  │  ┌────────────┐          ┌─────────────┐  │
  │  │ fetch()    │  bytes → │ parse()     │  │ → lille resultat
  │  │ await I/O  │          │ én pr. kerne│  │
  │  └────────────┘          └─────────────┘  │
  └───────────────────────────────────────────┘
```

Hele mønsteret står i én funktion:

```python
async def handle(i, in_flight, io_sem, pool):
    async with in_flight:                 # 1) backpressure: begræns RAM
        async with io_sem:                # 2) begræns samtidige forbindelser
            raw = await fetch(i)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(pool, parse, raw)  # 3) CPU i separat proces
```

## Hvorfor de skal holdes adskilt

**Parsing i event loopet** stopper loopet, mens der parses. Alle 200 ventende netværkskald står stille, og man ender med at lave cirka én ting ad gangen.

**Hentning i process-poolen** binder en hel proces til at vente på netværket. Med 8 kerner kan man så kun have 8 kald i gang i stedet for 200.

**Ét fælles loft** passer aldrig til begge dele. Sættes det til 200, får man 200 tunge parse-opgaver, der kæmper om 8 kerner. Sættes det til 8, venter man på netværket 8 kald ad gangen.

**Ingen lofter** betyder, at alle 10.000 dokumenter bliver hentet med det samme og ligger i RAM og venter på parseren.

## Målinger

10.000 dokumenter på ca. 54 KB, 50 ms simuleret I/O pr. dokument, 2 kerner:

| Variant | Tid | Docs/s | Peak RAM (hovedproces) |
|---|---|---|---|
| `naive` – parsing i event loopet | 8,3 s | 1.199 | 38 MB |
| **`adskilt` – med lofter** | **6,4 s** | **1.560** | **49 MB** |
| `nolimit` – adskilt uden lofter | 7,3 s | 1.366 | 578 MB |

- Med kun 2 kerner er tidsgevinsten beskeden. Den vokser nogenlunde med antallet af kerner.
- Den store forskel er RAM. Med lofter er hukommelsen bundet af `IN_FLIGHT`, ikke af antallet af dokumenter, så den holder sig også nede ved 1 million dokumenter.
- `naive` bruger lidt mindre RAM, fordi den aldrig når at have mange dokumenter liggende. Den er bare langsom.

## Detaljer der betyder noget for performance

- **Returnér noget lille fra `parse`.** Både input og output pickles og sendes mellem processerne.
- **`parse` skal være en top-level funktion**, ikke en lambda eller closure. Ellers kan den ikke pickles.
- **Opret poolen én gang og genbrug den.** Det tager ca. 50 ms at starte en ny proces.
- **Tasks der venter på en semaphore koster næsten intet.** 10.000 tasks er fint. Ved millioner af dokumenter kan man skifte til et fast antal workers, der læser fra en `asyncio.Queue`.

## Brug det på rigtige data

Udskift de to funktioner:

```python
async def fetch(i):       # fx httpx.AsyncClient().get(...) eller aiofiles
def parse(raw: bytes):    # fx PDF-/HTML-/JSON-parsing
```

Justér så de tre konstanter øverst i `pipeline.py`: `IO_LIMIT`, `CPU_WORKERS` og `IN_FLIGHT`.
