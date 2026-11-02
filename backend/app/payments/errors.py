"""Sanitised errors; provider bodies and credentials never cross this boundary."""


class PaymentError(Exception):
    code = "PAYMENT_ERROR"
    message = "Payment operation could not be completed."

    def __init__(self):
        super().__init__(self.message)


class ConfigurationError(PaymentError):
    code = "PAYMENT_CONFIGURATION_INVALID"
    message = "Payment configuration is invalid."


class InvalidRequest(PaymentError):
    code = "PAYMENT_REQUEST_INVALID"
    message = "Payment request is invalid."


class AuthError(PaymentError):
    code = "PAYMENT_AUTH_FAILED"
    message = "Payment provider authentication failed."


class RateLimited(PaymentError):
    code = "PAYMENT_RATE_LIMITED"
    message = "Payment provider rate limit reached."


class ProviderTimeout(PaymentError):
    code = "PAYMENT_STATUS_UNAVAILABLE"
    message = "Payment provider request timed out."


class ProviderUnavailable(PaymentError):
    code = "PAYMENT_STATUS_UNAVAILABLE"
    message = "Payment provider is unavailable."


class ProviderRejected(PaymentError):
    code = "PAYMENT_PROVIDER_REJECTED"
    message = "Payment provider rejected the operation."


class MalformedResponse(PaymentError):
    code = "PAYMENT_RESPONSE_INVALID"
    message = "Payment provider response could not be validated."


class RecoveryRequired(PaymentError):
    code = "PAYMENT_RECOVERY_REQUIRED"
    message = "An earlier operation needs reconciliation before another attempt."


class ApprovalRequired(PaymentError):
    code = "PAYMENT_APPROVAL_REQUIRED"
    message = "An authenticated human approval with a payer reference is required."


class InvalidWebhook(PaymentError):
    code = "PAYMENT_WEBHOOK_INVALID"
    message = "Webhook authenticity could not be verified."
