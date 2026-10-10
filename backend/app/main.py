"""Main application entrypoint for CashFlow AI 2.0 backend.

Can be run with:
    uvicorn backend.app.main:app --reload --port 8000
"""

from backend.app.api.app import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
