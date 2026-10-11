# IMAP_project: Django REST Framework vs FastAPI

The same small countries API built twice (Django REST Framework and FastAPI), then compared on
code size, speed, validation and auto-generated docs. Full write-up and research answers:
**[docs/COMPARISON.md](docs/COMPARISON.md)**.

## Headline results

| | DRF | FastAPI |
|---|---|---|
| Code lines | 101 (about 25 are Django bootstrap) | 50 |
| CRUD throughput (2 runs, 1 worker, in-memory data) | about 420-610 req/s | about 465-565 req/s, overlapping with DRF within run-to-run noise except on the 30-item list |
| p95 latency | about 44-59 ms | about 90-111 ms |
| 20 concurrent 0.2 s waits | 4.9 req/s (1 sync worker), 92 req/s (20 threads) | 94 req/s (async) |
| Invalid input status | 400, errors keyed by field | 422, list of `{loc, msg, type, input}` |
| Docs | needs `drf-spectacular` (OpenAPI 3.0.3) | built in `/docs`, `/redoc` (OpenAPI 3.1.0) |

## Important caveats

- **Data is a sample, not live REST Countries data.** The build sandbox could not reach
  restcountries.com, so `data/countries.json` holds 30 countries I wrote by hand from memory
  (populations and areas are approximate). Set `COUNTRIES_SOURCE=live` to load from the real API
  at startup instead (`data/loader.py`). That path is **untested against the real API**; only its
  field mapping was checked, against a payload I wrote in the documented v3.1 shape.
- Benchmarks ran on a 2-core sandbox with the load client on the same machine, one worker per server,
  no database. Run-to-run variance was up to about 30%. Treat the numbers as indicative, not as
  a general verdict on either framework.

## Layout

```
data/            countries.json (sample) + loader.py (sample or live)
drf_app/         project.py   single-file Django + DRF + drf-spectacular app
fastapi_app/     main.py      FastAPI app
benchmark/       bench.py, validation_compare.py, slow_threads.py, loc.py
results/         raw outputs: bench_run1/2.json, validation.json, OpenAPI specs, slow_threads.txt
docs/            COMPARISON.md
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# terminal 1: DRF on :8001 (docs: /api/docs/)
gunicorn --chdir drf_app project:application --workers 1 --bind 127.0.0.1:8001

# terminal 2: FastAPI on :8002 (docs: /docs)
uvicorn main:app --app-dir fastapi_app --workers 1 --port 8002

# optional, live data instead of the sample
COUNTRIES_SOURCE=live uvicorn main:app --app-dir fastapi_app --port 8002
```

Endpoints (both apps): `GET /countries?region=&search=&min_population=`,
`GET /countries/{code}`, `POST /countries`, `GET /slow?delay=0.2`.

## Reproduce the measurements

```bash
python benchmark/loc.py                  # code size
python benchmark/validation_compare.py   # same bad inputs to both (creates records)
# restart both servers here so the list is back to 30 items
python benchmark/bench.py                # load test, writes results/bench.json
# DRF with threads, for the /slow fairness check:
gunicorn --chdir drf_app project:application --workers 1 --threads 20 --bind 127.0.0.1:8003
python benchmark/slow_threads.py
```

Data is held in memory, so restart a server to reset its state.
