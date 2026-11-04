"""Main application entrypoint for CashFlow AI 2.0 backend.

Can be run with:
    python -m backend.app.main
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)

from backend.app.api.app import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, access_log=False)
