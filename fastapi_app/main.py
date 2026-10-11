"""Countries API built with FastAPI.

Run:  uvicorn main:app --app-dir fastapi_app --workers 1 --port 8002
Docs: http://127.0.0.1:8002/docs   (Swagger UI, built in)
"""
import asyncio
import sys
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Path as PathParam, Query
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
from loader import load_countries  # noqa: E402

Region = Literal["Africa", "Americas", "Asia", "Europe", "Oceania", "Antarctic"]


class Country(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cca2: str = Field(pattern=r"^[A-Z]{2}$")
    cca3: str = Field(pattern=r"^[A-Z]{3}$")
    region: Region
    capital: Optional[str] = Field(default=None, max_length=100)
    population: int = Field(ge=0)
    area: Optional[float] = Field(default=None, ge=0)


COUNTRIES = {c["cca2"]: c for c in load_countries()}
app = FastAPI(title="Countries API (FastAPI)", version="1.0.0")


@app.get("/countries", response_model=list[Country])
async def list_countries(
    region: Optional[Region] = None,
    search: Optional[str] = Query(default=None, max_length=50),
    min_population: Optional[int] = Query(default=None, ge=0),
):
    items = list(COUNTRIES.values())
    if region:
        items = [c for c in items if c["region"] == region]
    if search:
        items = [c for c in items if search.lower() in c["name"].lower()]
    if min_population is not None:
        items = [c for c in items if c["population"] >= min_population]
    return items


@app.post("/countries", response_model=Country, status_code=201)
async def create_country(country: Country):
    if country.cca2 in COUNTRIES:
        raise HTTPException(status_code=409, detail="Country already exists")
    COUNTRIES[country.cca2] = country.model_dump()
    return country


@app.get("/countries/{code}", response_model=Country)
async def get_country(code: str = PathParam(pattern=r"^[A-Za-z]{2,3}$")):
    code = code.upper()
    for c in COUNTRIES.values():
        if code in (c["cca2"], c["cca3"]):
            return c
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/slow")
async def slow(delay: float = Query(default=0.2, ge=0, le=1)):
    """Simulates a slow upstream call (non-blocking sleep, as an async view would do)."""
    await asyncio.sleep(delay)
    return {"slept": delay}
