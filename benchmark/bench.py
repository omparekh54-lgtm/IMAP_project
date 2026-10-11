"""Load-test both APIs with the same client, same endpoints, same concurrency.

Usage: python benchmark/bench.py   (servers must already be running on 8001 / 8002)
Writes results/bench.json
"""
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

TARGETS = {"DRF (gunicorn, 1 sync worker)": "http://127.0.0.1:8001",
           "FastAPI (uvicorn, 1 worker)": "http://127.0.0.1:8002"}
BAD_POST = {"name": "X", "cca2": "bad", "cca3": "BAD", "region": "Mars", "population": -5}

# name, method, path, json body, total requests, concurrency
SCENARIOS = [
    ("GET /countries/IN (detail)", "GET", "/countries/IN", None, 3000, 20),
    ("GET /countries (list of 30)", "GET", "/countries", None, 3000, 20),
    ("GET /countries?region=Asia&min_population=1000000", "GET",
     "/countries?region=Asia&min_population=1000000", None, 3000, 20),
    ("POST /countries (invalid body -> 4xx)", "POST", "/countries", BAD_POST, 3000, 20),
    ("GET /slow (0.2s simulated upstream)", "GET", "/slow?delay=0.2", None, 100, 20),
]


async def run(base, method, path, body, total, conc):
    sem = asyncio.Semaphore(conc)
    lat = []
    async with httpx.AsyncClient(base_url=base, limits=httpx.Limits(max_connections=conc)) as client:
        async def one():
            async with sem:
                t = time.perf_counter()
                r = await client.request(method, path, json=body)
                lat.append((time.perf_counter() - t) * 1000)
                return r.status_code

        await asyncio.gather(*[one() for _ in range(min(100, total))])  # warm-up
        lat.clear()
        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one() for _ in range(total)])
        wall = time.perf_counter() - t0
    lat.sort()
    return {
        "requests": total, "concurrency": conc, "status_codes": sorted(set(codes)),
        "rps": round(total / wall, 1), "wall_s": round(wall, 2),
        "p50_ms": round(statistics.median(lat), 2),
        "p95_ms": round(lat[int(len(lat) * 0.95) - 1], 2),
        "p99_ms": round(lat[int(len(lat) * 0.99) - 1], 2),
    }


async def main():
    out = {}
    for label, base in TARGETS.items():
        out[label] = {}
        for name, method, path, body, total, conc in SCENARIOS:
            res = await run(base, method, path, body, total, conc)
            out[label][name] = res
            print(f"{label:34} {name:52} {res['rps']:>8} rps  p50 {res['p50_ms']:>7} ms  "
                  f"p95 {res['p95_ms']:>7} ms  {res['status_codes']}")
    Path(__file__).resolve().parent.parent.joinpath("results", "bench.json").write_text(json.dumps(out, indent=2))


asyncio.run(main())
