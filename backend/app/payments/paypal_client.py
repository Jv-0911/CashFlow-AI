"""Narrow PayPal Sandbox client, with no arbitrary-URL request interface."""

import base64
from dataclasses import dataclass, field
import http.client
import json
import re
import socket
import ssl
from threading import Lock
import time
from uuid import UUID

from .config import PaymentConfig, SANDBOX_HOST
from .errors import (AuthError, InvalidRequest, MalformedResponse, ProviderRejected,
                     ProviderTimeout, ProviderUnavailable, RateLimited)
from .schemas import invoice_id, parse_invoice, parse_json

MAX_RESPONSE_BYTES = 1_048_576


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: bytes = field(repr=False)


def _allowed(method, path):
    if method == "POST" and path in {"/v1/oauth2/token", "/v2/invoicing/invoices",
                                      "/v2/invoicing/search-invoices", "/v1/notifications/verify-webhook-signature"}:
        return True
    return re.fullmatch(r"/v2/invoicing/invoices/INV2-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){3}" +
                        (r"/send" if method == "POST" else ""), path) is not None and method in {"GET", "POST"}


class SandboxTransport:
    """HTTPS only; TLS verified, redirects/proxies unsupported, bounded reads."""

    def request(self, method, path, headers, body, timeout_seconds):
        if not _allowed(method, path):
            raise InvalidRequest()
        connection = None
        result = None
        deadline = time.monotonic() + timeout_seconds
        try:
            context = ssl.create_default_context()
            connection = http.client.HTTPSConnection(SANDBOX_HOST, timeout=timeout_seconds, context=context)
            connection.connect()
            wire_socket = connection.sock
            def remaining():
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    raise ProviderTimeout()
                wire_socket.settimeout(remaining_time)
            remaining()
            connection.request(method, path, body=body, headers=headers)
            remaining()
            result = connection.getresponse()
            # No redirect is ever followed and no provider error body is read.
            if result.status >= 300:
                return Response(result.status, b"")
            chunks = []
            size = 0
            while True:
                # HTTPResponse can own the socket after Connection: close.
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    raise ProviderTimeout()
                wire_socket.settimeout(remaining_time)
                chunk = result.read1(min(65536, MAX_RESPONSE_BYTES + 1 - size))
                if not chunk:
                    if result.length not in (None, 0):
                        # A broken connection is not a complete invoice response.
                        raise ProviderUnavailable()
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise MalformedResponse()
            return Response(result.status, b"".join(chunks))
        except (TimeoutError, socket.timeout):
            raise ProviderTimeout() from None
        except (OSError, http.client.HTTPException):
            raise ProviderUnavailable() from None
        finally:
            if result is not None:
                result.close()
            if connection is not None:
                connection.close()


class PayPalClient:
    def __init__(self, config: PaymentConfig, *, transport=None, clock=time.monotonic, sleep=time.sleep):
        if type(config) is not PaymentConfig:
            raise InvalidRequest()
        config.__post_init__()
        self.config = config
        self._transport = SandboxTransport() if transport is None else transport
        self._clock, self._sleep = clock, sleep
        self._token = None
        self._expires_at = 0
        self._token_lock = Lock()

    def _send(self, method, path, headers, body, *, retry_safe):
        if not _allowed(method, path):
            raise InvalidRequest()
        for attempt in range(3 if retry_safe else 1):
            try:
                response = self._transport.request(method, path, headers, body, self.config.timeout_seconds)
                if type(response) is not Response or type(response.status) is not int or type(response.body) is not bytes or len(response.body) > MAX_RESPONSE_BYTES:
                    raise MalformedResponse()
                if response.status == 408:
                    raise ProviderTimeout()
                if response.status == 429:
                    raise RateLimited()
                # Redirects, conflicts and protocol surprises are not proof
                # that an invoice-changing request was definitely rejected.
                # Safe reads may retry; create/send never repeat here.
                if (response.status < 200 or response.status >= 500
                        or 300 <= response.status < 400 or response.status in {409, 425}):
                    raise ProviderUnavailable()
                return response
            except (RateLimited, ProviderUnavailable, ProviderTimeout):
                if not retry_safe or attempt == 2:
                    raise
                self._sleep(1 << attempt)

    def _access_token(self, *, invalid_token=None):
        with self._token_lock:
            if invalid_token is not None and self._token == invalid_token:
                self._token, self._expires_at = None, 0
            if self._token and self._clock() < self._expires_at:
                return self._token
            credentials = base64.b64encode((self.config.client_id + ":" + self.config.client_secret).encode()).decode("ascii")
            try:
                result = self._send("POST", "/v1/oauth2/token",
                                    {"Authorization": "Basic " + credentials, "Content-Type": "application/x-www-form-urlencoded"},
                                    b"grant_type=client_credentials", retry_safe=True)
            except MalformedResponse:
                raise AuthError() from None
            if result.status != 200:
                raise AuthError()
            # An invalid OAuth response is an authentication failure, not an
            # invoice observation. Verification must not change ledger state.
            try:
                payload = parse_json(result.body)
                token = payload.get("access_token")
                ttl = payload.get("expires_in")
                if (type(token) is not str or re.fullmatch(r"[A-Za-z0-9._~+/=-]{1,4096}", token) is None
                        or payload.get("token_type") != "Bearer" or type(ttl) is not int or not 1 <= ttl <= 86400):
                    raise MalformedResponse()
            except MalformedResponse:
                raise AuthError() from None
            self._token, self._expires_at = token, self._clock() + max(0, ttl - 30)
            return token

    def _api(self, method, path, *, data=None, request_id=None, retry_safe=False, success=(200,), before_dispatch=None):
        if not _allowed(method, path):
            raise InvalidRequest()
        body = None if data is None else json.dumps(data, allow_nan=False, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json", "Prefer": "return=representation"}
        def set_request_id(value):
            try:
                if type(value) is not str or str(UUID(value)) != value:
                    raise ValueError
            except (ValueError, AttributeError):
                raise InvalidRequest() from None
            headers["PayPal-Request-Id"] = value
        if before_dispatch is not None and (not callable(before_dispatch) or request_id is not None):
            raise InvalidRequest()
        if request_id is not None:
            set_request_id(request_id)
        token = self._access_token()
        if before_dispatch is not None:
            # Trusted service callback commits the durable claim after OAuth,
            # before any invoice-changing network call. Invoke exactly once;
            # a later 401 refresh does not acquire another claim or request ID.
            set_request_id(before_dispatch())
        for refresh in range(2):
            headers["Authorization"] = "Bearer " + token
            result = self._send(method, path, headers, body, retry_safe=retry_safe)
            if result.status == 401:
                if refresh:
                    raise AuthError()
                token = self._access_token(invalid_token=token)
                continue
            if result.status not in success:
                if result.status in {400, 403, 404, 405, 415, 422}:
                    raise ProviderRejected()
                # An unexpected success or undocumented error cannot justify
                # a terminal FAILED state. Preserve the durable claim/state.
                raise ProviderUnavailable()
            return parse_json(result.body) if result.body else {}
        raise AuthError()

    def get_invoice(self, provider_invoice_id):
        identity = invoice_id(provider_invoice_id)
        return parse_invoice(self._api("GET", "/v2/invoicing/invoices/" + identity, retry_safe=True))

    def create_invoice(self, payload, request_id=None, *, before_dispatch=None):
        if request_id is None and before_dispatch is None:
            raise InvalidRequest()
        # The endpoint's retention window is not documented. Never auto-repeat
        # an ambiguous POST; the durable operation is reconciled by reference.
        return parse_invoice(self._api("POST", "/v2/invoicing/invoices", data=payload,
                                       request_id=request_id, success=(201,), before_dispatch=before_dispatch))

    def send_invoice(self, provider_invoice_id, request_id=None, *, before_dispatch=None):
        identity = invoice_id(provider_invoice_id)
        if request_id is None and before_dispatch is None:
            raise InvalidRequest()
        self._api("POST", "/v2/invoicing/invoices/" + identity + "/send",
                  data={"send_to_recipient": True, "send_to_invoicer": False},
                  request_id=request_id, success=(200, 202, 204), before_dispatch=before_dispatch)

    def search_invoice_ids(self, number):
        if type(number) is not str or re.fullmatch(r"CF[A-F0-9]{23}", number) is None:
            raise InvalidRequest()
        result = self._api("POST", "/v2/invoicing/search-invoices", data={"invoice_number": number}, retry_safe=True)
        items = result.get("items", [])
        pages = result.get("total_pages", 1)
        if type(items) is not list or len(items) > 100 or type(pages) is not int or pages > 1:
            raise MalformedResponse()
        try:
            return tuple(invoice_id(item["id"]) for item in items)
        except (KeyError, TypeError, InvalidRequest):
            raise MalformedResponse() from None

    def verify_webhook_signature(self, payload):
        result = self._api("POST", "/v1/notifications/verify-webhook-signature", data=payload, retry_safe=True)
        return result.get("verification_status") == "SUCCESS"
