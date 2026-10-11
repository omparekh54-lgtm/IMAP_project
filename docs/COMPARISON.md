# Django REST Framework vs FastAPI: same API, built twice

Both apps expose the same four endpoints over the same 30-country dataset (`data/countries.json`,
same field names as REST Countries v3.1, flattened). Everything below was measured or observed in
this repo; raw outputs are in `results/`.

| Endpoint | What it exercises |
|---|---|
| `GET /countries` | list + filters `region`, `search`, `min_population` (query validation) |
| `GET /countries/{code}` | detail by 2- or 3-letter code (path validation, 404) |
| `POST /countries` | create with body validation (400/422, 409 on duplicate) |
| `GET /slow?delay=0.2` | simulated slow upstream call (sync vs async) |

## 1. Code size

Counted by `benchmark/loc.py` (blank lines, comments and docstrings excluded):

| | Code lines |
|---|---|
| DRF (`drf_app/project.py`) | **101** |
| FastAPI (`fastapi_app/main.py`) | **50** |

Caveat: a Django project is normally split across several files; I used a single-file project so
the counts are comparable, and about 25 of its 101 lines are Django settings and bootstrap that a
normal project would spread across `settings.py`, `urls.py` and `wsgi.py`. Without them DRF is roughly 75 lines, still about 50% more
than FastAPI. Most of the gap is that DRF needs a serializer class per input shape (country,
list-query params, slow-query params), whereas FastAPI declares the same constraints in type
hints on the function signature.

## 2. Speed

Same Python/httpx load client (`benchmark/bench.py`), concurrency 20, 3000 requests per scenario
after a 100-request warm-up, one server process each (DRF: gunicorn, 1 sync worker; FastAPI:
uvicorn, 1 worker), data in memory (no database). Two full runs, shown as run1 / run2:

Reading the table: req/s cells are `run1 / run2`; latency cells are `p50 run1 / run2 · p95 run1 / run2` in ms.

| Scenario | DRF req/s | FastAPI req/s | DRF p50 · p95 (ms) | FastAPI p50 · p95 (ms) |
|---|---|---|---|---|
| `GET /countries/IN` | 519 / 613 | 566 / 520 | 38 / 30 · 50 / 44 | 25 / 27 · 90 / 97 |
| `GET /countries` (30 items) | 421 / 421 | 551 / 529 | 47 / 47 · 59 / 58 | 27 / 28 · 92 / 94 |
| `GET /countries?region=Asia&min_population=1000000` | 504 / 496 | 532 / 464 | 39 / 40 · 52 / 53 | 27 / 31 · 95 / 111 |
| `POST /countries` (invalid body) | 498 / 507 | 473 / 506 | 39 / 37 · 53 / 53 | 31 / 29 · 104 / 100 |
| `GET /slow` (0.2 s), 1 sync worker | **4.9 / 4.9** | **93.8 / 93.7** | 4052 / 4056 p50 | 206 / 205 p50 |
| `GET /slow`, DRF with 20 gunicorn threads | **92.2** (1 run) | n/a | 207 p50 / 239 p95 | n/a |

What this does and does not show:

- **Plain CRUD throughput is roughly a tie.** The two committed runs already differ by 13-18% on
  the same server (DRF detail 519 vs 613; FastAPI filter 532 vs 464), and an earlier run of this
  benchmark, made before a small refactor and not kept in the repo, swung by as much as ~30%. That
  noise is larger than most of the differences above. The one gap that held in both runs is the
  30-item list, where FastAPI was ~25-30% ahead. I did not profile why.
- **Latency shape differs.** FastAPI had the lower median (~25-31 ms vs ~30-47 ms) but about
  twice the p95 (~90-110 ms vs ~44-59 ms) in every run. I did not diagnose the cause.
- **The `/slow` result is a configuration effect, not a framework verdict.** One synchronous
  worker can only wait on one request at a time, so 20 concurrent 0.2 s waits queue up (4.9 req/s).
  Giving the same DRF app 20 threads brings it to 92 req/s, within noise of FastAPI's async
  event loop. Async's real advantage is holding *many thousands* of idle waits cheaply, which this
  test (20 concurrent) does not reach.
- **Limits of the test:** the sandbox had 2 CPU cores shared by the load client and the server,
  so the client may cap throughput near ~500 req/s for both; there is no database, so DRF's
  ORM integration and FastAPI-with-an-ORM were not compared; one worker each; no network latency.

## 3. Validation

Same rules in both: `cca2` = 2 uppercase letters, `cca3` = 3 uppercase letters, `region` in a fixed
list, `population >= 0`, name 1-100 chars. Same 15 requests sent to both
(`benchmark/validation_compare.py`, output in `results/validation.json`):

| | DRF serializers | FastAPI + Pydantic |
|---|---|---|
| Invalid body / query / path | **400** | **422** |
| Duplicate, not found | 409, 404 | 409, 404 |
| Error shape | `{"cca2": ["This field is required."]}`, keyed by field | `{"detail": [{"type", "loc", "msg", "input"}]}`, a list with a location path |
| `"5"` for an int field | accepted, coerced to 5 | accepted, coerced to 5 |
| Unknown extra field | silently ignored | silently ignored |
| Malformed JSON | 400 | 422 |
| Query/path params | needed a separate serializer plus a manual check for the path code | declared in the function signature (`Query(ge=0)`, `Path(pattern=...)`) |

Notes: both frameworks coerce loosely by default (Pydantic's strict mode and DRF custom fields
can tighten that). FastAPI's 422 body echoes the submitted `input` back, which matters if a
request can contain secrets and error bodies get logged or shown.

## 4. Auto-generated docs

| | DRF | FastAPI |
|---|---|---|
| Setup | third-party `drf-spectacular` (+ `pyyaml`, `uritemplate`), 2 settings, 2 routes, a template engine for the Swagger page | none; `/docs` (Swagger UI), `/redoc` and `/openapi.json` exist by default |
| Spec version | OpenAPI 3.0.3 | OpenAPI 3.1.0 |
| Where it learns the contract | serializers, plus `@extend_schema` for query params and non-serializer responses | type hints, `Field`, `Query`, `Path`, `response_model` |
| Error responses | not documented unless added by hand | 422 `HTTPValidationError` schema included automatically |
| Rough edges seen | the schema endpoint listed itself as an operation (could be excluded) | none |

Both specs describe the same `Country` model with matching constraints (pattern, minimum,
required fields); see `results/drf_openapi.yaml` and `results/fastapi_openapi.json`.

## 5. Research questions

### Sync vs async: what is different?

A sync view occupies one worker (process or thread) for its whole life. When it blocks on a
database or HTTP call, that worker does nothing else, so concurrency equals worker-count x threads.
An async view runs on an event loop: at each `await` it hands control back, so one process can
interleave many requests that are mostly waiting on I/O. That's what the `/slow` test shows:
1 sync worker = 4.9 req/s, 20 threads = 92 req/s, async event loop = 94 req/s.

Async does not make CPU work faster, and a *blocking* call inside an `async def` (a sync DB driver,
`time.sleep`, `requests.get`) stalls the whole loop, which is the classic FastAPI pitfall. FastAPI
runs plain `def` endpoints in a threadpool, so you can mix both. Django supports ASGI and async
views, but as far as I know DRF's own view layer is still synchronous (community packages such as
`adrf` add async), so a DRF app typically scales I/O waits with threads or more workers.

### How does each validate data?

- **DRF serializers** are classes with typed fields (`IntegerField(min_value=0)`,
  `RegexField`, `ChoiceField`). `is_valid()` runs per-field validation then `validate()` hooks,
  and the same class also converts objects to JSON for output. With `ModelSerializer` it is
  generated from Django models, which is the big win when you have a database.
- **Pydantic** models use ordinary type annotations plus `Field(...)` constraints; FastAPI
  parses the request into the model before your function runs and returns 422 automatically.
  Pydantic v2's core is written in Rust. The same model type doubles as the OpenAPI schema and as
  the response model, so docs, validation and serialization cannot drift apart.

### Where would you choose each?

Choose **DRF** when the project is database-centric and already Django: you want the ORM,
migrations, admin, auth, permissions, throttling and `ModelSerializer`/`ModelViewSet` to give
you CRUD with very little code, or the team already knows Django.
Choose **FastAPI** for a new service where the API contract is the product: type-hint-driven
validation and docs, a smaller footprint, async I/O (calling other services, websockets, streaming),
or an ML/microservice endpoint. In this experiment CRUD throughput did not separate them; the
decisive differences were ergonomics (50 vs ~100 lines, zero-config docs) and what surrounds the
API (Django's batteries vs assembling your own).

## 6. Reproducing

See the README. In short: start both servers, run `benchmark/validation_compare.py` first (it
creates records), then **restart both servers** so the list has 30 items again, then run
`benchmark/bench.py`.
