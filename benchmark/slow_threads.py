"""Fairness check for /slow: DRF under gunicorn with 20 threads (port 8003) vs the earlier 1-sync-worker run.

Start the server first:
  gunicorn --chdir drf_app project:application --workers 1 --threads 20 --bind 127.0.0.1:8003
Usage: python benchmark/slow_threads.py
"""
import asyncio
import time

import httpx


async def main(base="http://127.0.0.1:8003", total=100, conc=20):
    sem = asyncio.Semaphore(conc)
    lat = []
    async with httpx.AsyncClient(base_url=base, limits=httpx.Limits(max_connections=conc)) as c:
        async def one():
            async with sem:
                t = time.perf_counter()
                r = await c.get("/slow?delay=0.2")
                lat.append((time.perf_counter() - t) * 1000)
                return r.status_code
        await asyncio.gather(*[one() for _ in range(20)])  # warm-up
        lat.clear()
        t0 = time.perf_counter()
        codes = await asyncio.gather(*[one() for _ in range(total)])
        wall = time.perf_counter() - t0
    lat.sort()
    print(f"DRF gunicorn 1 worker x 20 threads: {total / wall:.1f} rps, p50 {lat[len(lat)//2]:.1f} ms, "
          f"p95 {lat[int(len(lat)*0.95)-1]:.1f} ms, codes {sorted(set(codes))}")


asyncio.run(main())
