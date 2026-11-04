# Persistent backend only. Member 4's frontend is deployed separately on Vercel.
FROM python:3.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LEDGER_DB_PATH=/app/data/ledger.db
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
COPY backend/constraints.txt ./backend/constraints.txt
RUN pip install --no-cache-dir -r backend/requirements.txt && useradd --uid 10001 --create-home cashflow
COPY backend/app/ ./backend/app/
COPY contracts/ ./contracts/
RUN mkdir -p /app/data && chown -R cashflow:cashflow /app
USER cashflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
