"""Optional webhook adapter. Signature verified remotely; body never sets state."""

from datetime import datetime
import re
from urllib.parse import urlsplit

from ..ledger.models import require_identifier
from ..ledger.errors import InvalidInput
from .errors import InvalidRequest, InvalidWebhook, MalformedResponse
from .schemas import invoice_id, parse_json
from .verification import VerificationService


class WebhookHandler:
    def __init__(self, ledger, client):
        self.ledger, self.client = ledger, client
        self.verifier = VerificationService(ledger, client)

    def handle(self, raw_body: bytes, headers):
        if not self.client.config.webhook_id or type(raw_body) is not bytes or not 0 < len(raw_body) <= 262144:
            raise InvalidWebhook()
        try:
            event = parse_json(raw_body)
            lowered = {}
            for key, value in headers.items():
                if type(key) is not str or type(value) is not str:
                    raise InvalidWebhook()
                name = key.lower()
                if name in lowered or any(ord(c) < 32 for c in value):
                    raise InvalidWebhook()
                lowered[name] = value
            payload = {field: lowered[header] for field, header in {
                "auth_algo": "paypal-auth-algo", "cert_url": "paypal-cert-url",
                "transmission_id": "paypal-transmission-id", "transmission_sig": "paypal-transmission-sig",
                "transmission_time": "paypal-transmission-time"}.items()}
            if payload["auth_algo"] != "SHA256withRSA":
                raise InvalidWebhook()
            if not 1 <= len(payload["transmission_sig"]) <= 500 or not 1 <= len(payload["transmission_id"]) <= 50:
                raise InvalidWebhook()
            if len(payload["transmission_time"]) > 100 or datetime.fromisoformat(payload["transmission_time"].replace("Z", "+00:00")).tzinfo is None:
                raise InvalidWebhook()
            cert = urlsplit(payload["cert_url"])
            if (len(payload["cert_url"]) > 500 or cert.scheme != "https"
                    or cert.hostname not in {"api.sandbox.paypal.com", "api-m.sandbox.paypal.com"}
                    or cert.port not in (None, 443) or cert.username or cert.password or cert.query or cert.fragment
                    or re.fullmatch(r"/v1/notifications/certs/[A-Za-z0-9_-]+", cert.path) is None):
                raise InvalidWebhook()
            payload["webhook_id"] = self.client.config.webhook_id
            payload["webhook_event"] = event
            if not self.client.verify_webhook_signature(payload):
                raise InvalidWebhook()
            # Only after SUCCESS do identifiers influence local processing.
            event_id = event["id"]
            require_identifier(event_id)
            event_type = event["event_type"]
            if type(event_type) is not str or not event_type.startswith("INVOICING.INVOICE."):
                return "ignored"
            resource = event["resource"]
            direct = resource.get("id")
            nested = resource.get("invoice", {}).get("id")
            if direct and nested and direct != nested:
                raise InvalidWebhook()
            identity = invoice_id(nested or direct)
        except (KeyError, TypeError, AttributeError, ValueError, InvalidRequest, InvalidInput, MalformedResponse):
            raise InvalidWebhook() from None
        entry_id, disposition = self.ledger._store._claim_webhook(event_id, identity)
        if entry_id is None:
            return disposition
        self.verifier.verify(entry_id)
        return "processed"
