"""Send the same good and bad requests to both APIs and compare status codes and error shapes.

Usage: python benchmark/validation_compare.py   (servers must be running on 8001 / 8002)
Writes results/validation.json
"""
import json
from pathlib import Path

import httpx

GOOD = {"name": "Testland", "cca2": "TL", "cca3": "TST", "region": "Europe",
        "capital": "Testville", "population": 1000, "area": 12.5}
CASES = [
    ("valid POST", "POST", "/countries", {**GOOD, "cca2": "TL"}),
    ("duplicate POST (same cca2)", "POST", "/countries", {**GOOD, "cca2": "TL"}),
    ("missing required fields", "POST", "/countries", {"name": "Only a name"}),
    ("cca2 not 2 uppercase letters", "POST", "/countries", {**GOOD, "cca2": "tl1"}),
    ("region not in allowed list", "POST", "/countries", {**GOOD, "cca2": "TB", "cca3": "TTB", "region": "Mars"}),
    ("negative population", "POST", "/countries", {**GOOD, "cca2": "TC", "cca3": "TTC", "population": -1}),
    ("population wrong type (string)", "POST", "/countries", {**GOOD, "cca2": "TD", "cca3": "TTD", "population": "lots"}),
    ("population numeric string '5' (coercion)", "POST", "/countries", {**GOOD, "cca2": "TE", "cca3": "TTE", "population": "5"}),
    ("unknown extra field", "POST", "/countries", {**GOOD, "cca2": "TF", "cca3": "TTF", "flag": "x"}),
    ("malformed JSON body", "POST", "/countries", "{not json"),
    ("GET bad region query", "GET", "/countries?region=Mars", None),
    ("GET min_population=abc", "GET", "/countries?min_population=abc", None),
    ("GET unknown code", "GET", "/countries/ZZ", None),
    ("GET malformed code 'XX1'", "GET", "/countries/XX1", None),
    ("GET /slow?delay=99 (out of range)", "GET", "/slow?delay=99", None),
]
TARGETS = {"DRF": "http://127.0.0.1:8001", "FastAPI": "http://127.0.0.1:8002"}


def call(client, method, path, body):
    if isinstance(body, str):
        r = client.request(method, path, content=body, headers={"content-type": "application/json"})
    else:
        r = client.request(method, path, json=body)
    try:
        payload = r.json()
    except Exception:
        payload = r.text[:80]
    return r.status_code, payload


results = {}
for label, base in TARGETS.items():
    with httpx.Client(base_url=base, timeout=10) as client:
        results[label] = {name: call(client, m, p, b) for name, m, p, b in CASES}

print(f"{'case':44} {'DRF':>5} {'FastAPI':>8}")
for name, *_ in CASES:
    d, f = results["DRF"][name][0], results["FastAPI"][name][0]
    print(f"{name:44} {d:>5} {f:>8}{'   <-- differs' if d != f else ''}")
print("\nExample error body, 'missing required fields':")
for label in TARGETS:
    print(f"  {label}: {json.dumps(results[label]['missing required fields'][1])[:300]}")

Path(__file__).resolve().parent.parent.joinpath("results", "validation.json").write_text(json.dumps(results, indent=2))
