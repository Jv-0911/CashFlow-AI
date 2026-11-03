"""Single-origin application factory with explicit payment and authentication boundaries."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .application import Services, router as application_router
from .limits import RequestLimits
from .routes import router as demo_router
from .security import Settings
from ..ledger.errors import LedgerError, EntryNotFound, InvalidInput, IntegrityViolation, StorageUnavailable
from ..payments.contracts import error_view
from ..payments.errors import PaymentError, InvalidRequest


def create_app(settings=None, *, ledger=None, payments=None):
    settings = settings or Settings.from_env()
    svc = Services(settings, ledger=ledger, payments=payments)

    @asynccontextmanager
    async def lifespan(app):
        svc.start()
        stop = asyncio.Event()

        async def sweep():
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.reconciliation_seconds)
                except TimeoutError:
                    try:
                        await asyncio.to_thread(svc.payments.reconciliation.sweep)
                    except (PaymentError, LedgerError):
                        pass
        worker = asyncio.create_task(sweep()) if svc.payments else None
        try:
            yield
        finally:
            stop.set()
            if worker:
                await worker

    app = FastAPI(title='CashFlow AI', version='1.0.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.services = svc

    def error(request, status, code, message):
        return JSONResponse({'error': {'code': code, 'message': message,
            'request_id': getattr(request.state, 'request_id', 'req_'+uuid4().hex)}}, status_code=status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        messages = {
            'SIGN_IN_REQUIRED': 'Sign in to access this business ledger.',
            'LOGIN_FAILED': 'The password was not accepted.',
            'LOGIN_RATE_LIMITED': 'Too many sign-in attempts. Try again in a minute.',
            'ACTION_RATE_LIMITED': 'Too many actions. Wait a minute and refresh the ledger.',
            'ADMIN_ACCESS_NOT_CONFIGURED': 'Administrator access has not been configured. Analysis remains read-only.',
            'SANDBOX_NOT_CONFIGURED': 'PayPal Sandbox is not configured. No invoice was sent or payment verified.',
            'EXPLICIT_APPROVAL_REQUIRED': 'Explicit human approval is required.',
        }
        code = exc.detail if isinstance(exc.detail, str) and exc.detail in {
            *messages, 'REQUEST_ORIGIN_INVALID', 'CSRF_CHECK_FAILED', 'SESSION_LIMIT_REACHED',
            'INVALID_HORIZON', 'SCENARIO_EVENT_INVALID', 'RECEIVABLE_NOT_FOUND'} else 'REQUEST_FAILED'
        return error(request, exc.status_code, code, messages.get(code, 'The request could not be completed.'))

    @app.exception_handler(RequestValidationError)
    async def invalid_body(request, exc):
        return error(request, 422, 'REQUEST_INVALID', 'Check the required fields and allowed values.')

    @app.exception_handler(PaymentError)
    @app.exception_handler(LedgerError)
    async def domain_error(request, exc):
        status = 503
        if isinstance(exc, EntryNotFound):
            status = 404
        elif isinstance(exc, (InvalidInput, InvalidRequest)):
            status = 422
        elif isinstance(exc, LedgerError) and not isinstance(exc, (IntegrityViolation, StorageUnavailable)):
            status = 409
        return JSONResponse(error_view(exc, request.state.request_id), status_code=status)

    @app.middleware('http')
    async def response_security(request: Request, call_next):
        request.state.request_id = 'req_'+uuid4().hex
        try:
            response = await call_next(request)
        except Exception:
            response = error(request, 500, 'INTERNAL_ERROR', 'The request could not be completed safely.')
        response.headers.update({
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'X-Request-ID': request.state.request_id,
        })
        if settings.secure_cookie:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    app.add_middleware(RequestLimits)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(settings.origin).hostname, 'localhost', '127.0.0.1'])
    app.include_router(demo_router)
    app.include_router(application_router)
    dist = Path(__file__).resolve().parents[3] / 'frontend' / 'dist'
    if dist.is_dir():
        app.mount('/assets', StaticFiles(directory=dist/'assets'), name='assets')

    @app.get('/', include_in_schema=False)
    def index():
        if not (dist/'index.html').is_file():
            return JSONResponse({'message': 'Build the frontend with npm run build in frontend/.'}, status_code=503)
        return FileResponse(dist/'index.html')
    return app


app = create_app()
