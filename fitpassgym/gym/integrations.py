from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class PaymentResult:
    successful: bool
    reference: str


class FakePaymentGateway:
    """Deterministic local adapter. Replace through FITPASS_PAYMENT_GATEWAY."""

    def charge(self, *, amount, currency, payment_token, idempotency_key):
        return PaymentResult(bool(payment_token), f"pay_{idempotency_key}")


class FakeDoorGateway:
    def grant_access(self, *, gym_id, user_id):
        return f"door_{gym_id}_{user_id}_{uuid4().hex[:8]}"
