# Async dokumentbehandling

Et lille eksempel på, hvordan man behandler 10.000 dokumenter hurtigt uden at sprænge maskinen. Eksemplet bruger kun Pythons standardbibliotek: [asyncio](https://docs.python.org/3/library/asyncio.html) til I/O og [ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor) til CPU-arbejde.

Hvert dokument skal først hentes (I/O) og derefter parses (CPU). Hver fil er én måde at gøre det på:

- `naive.py` henter med asyncio og parser direkte i event loopet.
- `unbounded.py` parser i en process pool, men har ingen lofter, så alle dokumenter hentes med det samme.
- `bounded.py` holder I/O og CPU adskilt, med en semaphore til I/O, en process pool til parsing og et loft over, hvor mange dokumenter der ligger i hukommelsen.

`docs.py` indeholder det, de tre filer deler: et simuleret `fetch` og et `parse`.

`bounded.py` er den, man skal bruge.

## Hvorfor I/O og CPU skal holdes adskilt

I/O er ventetid. Det koster næsten ingenting at vente, så asyncio kan have hundredvis af kald i gang på én tråd.

CPU er arbejde. Python kan kun køre én tråd ad gangen pr. proces (GIL), så parsing skal ud i separate processer, én pr. kerne.

Blandes de, går det galt:
- Parser man i event loopet, står alle ventende netværkskald stille, mens der parses.
- Henter man i process-poolen, bindes en hel proces til at vente. Med 8 kerner kan man så kun have 8 kald i gang.
- Bruger man ét fælles loft, passer det aldrig til begge dele: 200 er for mange til CPU'en, og 8 er for få til netværket.

## Fordele og ulemper

### Naiv (`naive.py`)

Fordele:
- Den er den enkleste.
- Den bruger mindst RAM.

Ulemper:
- Den bruger kun én kerne.
- Mens der parses, står alle netværkskald stille.

### Uden lofter (`unbounded.py`)

Fordele:
- Den bruger alle kerner.
- Den er stadig meget enkel.

Ulemper:
- Alle dokumenter hentes med det samme og ligger i RAM og venter på parseren. Ved 1 million dokumenter løber maskinen tør for hukommelse.
- Den åbner lige så mange forbindelser, som der er dokumenter. Det kan en rigtig server ikke holde til.

### Med lofter (`bounded.py`)

Fordele:
- Den bruger alle kerner.
- Hvor meget dokumenterne fylder i RAM, afhænger af lofterne, ikke af antallet af dokumenter.
- Antallet af samtidige forbindelser er styret.

Ulemper:
- Der er tre tal, der skal justeres: `IO_LIMIT`, `CPU_WORKERS` og `IN_FLIGHT`.
- Hvert dokument pickles og sendes til en anden proces. Hvis parsing er meget let, kan det koste mere end det sparer.

## Målinger

10.000 dokumenter på ca. 54 KB, 50 ms simuleret netværk og ca. 2 ms parsing pr. dokument, på en maskine med 2 kerner:

| Fil | Tid | Docs/s | Peak RAM |
|---|---|---|---|
| `naive.py` | 18,0 s | 555 | 36 MB |
| `unbounded.py` | 12,9 s | 777 | 576 MB |
| `bounded.py` | 13,7 s | 729 | 47 MB |

Med flere kerner bliver `unbounded.py` og `bounded.py` hurtigere, men `naive.py` gør ikke. `bounded.py` er en anelse langsommere end `unbounded.py`, til gengæld bruger den 12 gange mindre RAM.

## Kør

Kræver Python 3.9 eller nyere.

```
python naive.py
python unbounded.py
python bounded.py
```

Peak RAM vises kun på Linux.
