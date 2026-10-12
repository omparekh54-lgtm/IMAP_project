"""Vercel entrypoint for the IMAP FastAPI comparison app."""
from fastapi_app.main import app


@app.get("/", include_in_schema=False)
async def project_home():
    return {
        "project": "IMAP — Django REST Framework vs FastAPI",
        "deployed_api": "FastAPI",
        "docs": "/docs",
        "countries": "/countries",
        "comparison": "See docs/COMPARISON.md in the GitHub repository",
    }
