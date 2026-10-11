"""Load countries from the bundled sample (default) or live from REST Countries.

    COUNTRIES_SOURCE=live  ->  GET https://restcountries.com/v3.1/all?fields=...

The live path is NOT exercised in the sandbox this project was built in (outbound access to
restcountries.com was blocked there); only the field mapping is unit-checked against a payload
written in the documented REST Countries v3.1 shape. Treat live mode as untested against the real API.
"""
import json
import os
import urllib.request
from pathlib import Path

SAMPLE_FILE = Path(__file__).with_name("countries.json")
LIVE_URL = "https://restcountries.com/v3.1/all?fields=name,cca2,cca3,region,capital,population,area"
REGIONS = {"Africa", "Americas", "Asia", "Europe", "Oceania", "Antarctic"}


def from_restcountries(items):
    """Map REST Countries v3.1 records onto this project's flat schema."""
    out = []
    for c in items:
        if c.get("region") not in REGIONS:
            continue
        capital = c.get("capital") or [""]
        out.append({
            "name": c["name"]["common"],
            "cca2": c["cca2"],
            "cca3": c["cca3"],
            "region": c["region"],
            "capital": capital[0],
            "population": int(c.get("population", 0)),
            "area": float(c.get("area", 0)),
        })
    return out


def load_countries():
    if os.environ.get("COUNTRIES_SOURCE", "sample").lower() == "live":
        with urllib.request.urlopen(LIVE_URL, timeout=20) as resp:
            return from_restcountries(json.load(resp))
    return json.loads(SAMPLE_FILE.read_text())
