import pytest

from vanna_core.privacy import (
    bucket_latency,
    bucket_notional,
    pseudonymize,
    validate_shared_payload,
)


def test_pseudonym_is_stable_and_keyed() -> None:
    first = pseudonymize("desk-a-secret", "order-123")
    assert first == pseudonymize("desk-a-secret", "order-123")
    assert first != pseudonymize("desk-b-secret", "order-123")
    assert "order-123" not in first


def test_buckets_remove_precision() -> None:
    assert bucket_notional(2_400_123) == "1m-5m"
    assert bucket_latency(81.7) == "slow"


def test_shared_payload_rejects_local_identifiers() -> None:
    with pytest.raises(ValueError, match="prohibited"):
        validate_shared_payload({"pair": "EUR/USD", "client_id": "secret"})
