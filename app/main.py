"""Vercel entrypoint for the IMAP FastAPI comparison app.

The original DRF and FastAPI implementations remain unchanged. This module exposes
FastAPI at Vercel's conventional Python entrypoint and serves the interactive dashboard.
"""
from pathlib import Path

from fastapi.responses import HTMLResponse
from fastapi_app.main import app


DASHBOARD_PATH = Path(__file__).with_name("dashboard.html")


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def project_home():
    return DASHBOARD_PATH.read_text(encoding="utf-8")
