# CashFlow-AI
AI-Powered cash-flow forecasting and recovery assistant for small businesses.

---

## Backend API & Development Setup

### Python Environment
The backend uses a Windows virtual environment located at `backend/.venv-win` powered by Python 3.13.14.

### Running Automated Tests
From the project root:
```powershell
& ".\backend\.venv-win\Scripts\python.exe" -m pytest backend/tests -v
```
Or from the `backend/` directory:
```powershell
cd backend
& ".\.venv-win\Scripts\python.exe" -m pytest tests -v
```

### Running the API Server Locally
To start the FastAPI development server with hot-reload:
```powershell
& ".\backend\.venv-win\Scripts\python.exe" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive API documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Initial API Endpoints
- `GET /health` / `GET /api/v1/health`: Returns health status `{"status": "ok", "version": "0.1.0"}`.
- `GET /api/v1/forecast/demo`: Returns clearly labeled demo forecast fixture matching `contracts/forecast-response.example.json`.
- `GET /api/v1/forecast`: Alias returning demo fixture until the forecasting calculation engine in `backend/app/forecast/` is completed by Member 1.
