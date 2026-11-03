"""Single-business authentication. No credentials or request bodies are logged."""
from dataclasses import dataclass, field
import hashlib
import hmac
import os
import secrets
from threading import Lock
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Settings:
    password: str = field(default='', repr=False)
    origin: str = 'http://127.0.0.1:8000'
    db_path: str = 'data/ledger.db'
    paypal_enabled: bool = False
    ai_enabled: bool = False
    reconciliation_seconds: int = 60

    def __post_init__(self):
        url = urlsplit(self.origin)
        local = url.hostname in {'localhost', '127.0.0.1', '::1'}
        if (url.scheme not in {'http', 'https'} or not url.netloc or url.username
                or url.password or url.path or url.query or url.fragment
                or (not local and (url.scheme != 'https' or not self.password))):
            raise ValueError('Configure an HTTPS public origin and administrator password.')
        if self.password and not 12 <= len(self.password) <= 256:
            raise ValueError('Administrator password must contain 12 to 256 characters.')
        if self.paypal_enabled and not self.password:
            raise ValueError('Payment access requires administrator authentication.')
        if self.ai_enabled and not self.password:
            raise ValueError('External AI access requires administrator authentication.')
        if not self.db_path or self.db_path == ':memory:':
            raise ValueError('Configure a persistent ledger path.')
        if not 30 <= self.reconciliation_seconds <= 3600:
            raise ValueError('Reconciliation interval must be between 30 and 3600 seconds.')

    @classmethod
    def from_env(cls):
        if os.environ.get('PAYPAL_MODE', 'sandbox') != 'sandbox':
            raise ValueError('Only PayPal Sandbox is supported.')
        from ..payments.config import SANDBOX_BASE_URL, SANDBOX_HOST
        for key, value in os.environ.items():
            if key.startswith('PAYPAL_') and (key.endswith('URL') or key.endswith('HOST')):
                if value != (SANDBOX_HOST if key.endswith('HOST') else SANDBOX_BASE_URL):
                    raise ValueError('Only the pinned PayPal Sandbox destination is supported.')
        enabled = os.environ.get('CASHFLOW_PAYPAL_ENABLED', 'false')
        ai_enabled = os.environ.get('CASHFLOW_AI_ENABLED', 'false')
        if enabled not in {'true', 'false'} or ai_enabled not in {'true', 'false'}:
            raise ValueError('Integration enable flags must be true or false.')
        return cls(password=os.environ.get('CASHFLOW_ADMIN_PASSWORD', ''),
                   origin=os.environ.get('CASHFLOW_PUBLIC_ORIGIN', 'http://127.0.0.1:8000'),
                   db_path=os.environ.get('LEDGER_DB_PATH', 'data/ledger.db'),
                   paypal_enabled=enabled == 'true', ai_enabled=ai_enabled == 'true')

    @property
    def secure_cookie(self):
        return self.origin.startswith('https://')


class Sessions:
    def __init__(self, settings):
        self.settings = settings
        self.salt = secrets.token_bytes(16)
        self.expected = self._digest(settings.password) if settings.password else None
        self.sessions = {}
        self.attempts = {}
        self.writes = {}
        self.lock = Lock()

    def _digest(self, value):
        return hashlib.scrypt(value.encode(), salt=self.salt, n=16384, r=8, p=1)

    def origin_check(self, request):
        if request.headers.get('origin') != self.settings.origin:
            raise HTTPException(403, 'REQUEST_ORIGIN_INVALID')

    def login(self, request, password):
        self.origin_check(request)
        if self.expected is None:
            raise HTTPException(503, 'ADMIN_ACCESS_NOT_CONFIGURED')
        now = time.monotonic()
        identity = request.client.host if request.client else 'unknown'
        with self.lock:
            self.attempts = {k: v for k, v in self.attempts.items() if now - v[0] < 60}
            stamp, count = self.attempts.get(identity, (now, 0))
            if count >= 5 or (identity not in self.attempts and len(self.attempts) >= 1000):
                raise HTTPException(429, 'LOGIN_RATE_LIMITED')
            self.attempts[identity] = (stamp, count + 1)
        if not hmac.compare_digest(self._digest(password), self.expected):
            raise HTTPException(401, 'LOGIN_FAILED')
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v[0] > now}
            if len(self.sessions) >= 100:
                raise HTTPException(429, 'SESSION_LIMIT_REACHED')
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self.sessions[token] = (now + 1800, csrf)
        return token, csrf

    def get(self, request):
        token = request.cookies.get('cashflow_session', '')
        with self.lock:
            record = self.sessions.get(token)
            if record and record[0] <= time.monotonic():
                self.sessions.pop(token, None)
                record = None
            return record

    def require(self, request, *, write=False):
        record = self.get(request)
        if record is None:
            raise HTTPException(401, 'SIGN_IN_REQUIRED')
        if write:
            self.origin_check(request)
            if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), record[1]):
                raise HTTPException(403, 'CSRF_CHECK_FAILED')
            now = time.monotonic()
            token = request.cookies.get('cashflow_session')
            with self.lock:
                self.writes = {k: v for k, v in self.writes.items() if now - v[0] < 60}
                stamp, count = self.writes.get(token, (now, 0))
                if count >= 30:
                    raise HTTPException(429, 'ACTION_RATE_LIMITED')
                self.writes[token] = (stamp, count + 1)
        return 'business_owner'

    def logout(self, request):
        self.require(request, write=True)
        with self.lock:
            self.sessions.pop(request.cookies.get('cashflow_session'), None)
