"""Tests for the desk-local privacy helpers wired into the federation ClientApp."""

import pytest

from vanna_federation.privacy import (
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


def test_pseudonym_requires_inputs() -> None:
    with pytest.raises(ValueError):
        pseudonymize("", "order-123")
    with pytest.raises(ValueError):
        pseudonymize("desk-a-secret", "")


def test_buckets_remove_precision() -> None:
    assert bucket_notional(500_000) == "<1m"
    assert bucket_notional(2_400_123) == "1m-5m"
    assert bucket_notional(7_000_000) == "5m-10m"
    assert bucket_notional(20_000_000) == ">10m"
    assert bucket_latency(10.0) == "fast"
    assert bucket_latency(50.0) == "normal"
    assert bucket_latency(81.7) == "slow"


def test_shared_payload_allows_clean_metrics() -> None:
    # The exact metric payloads the ClientApp emits must pass.
    validate_shared_payload(
        {"train_loss": 0.51, "num-examples": 360, "raw-records-shared": 0}
    )
    validate_shared_payload(
        {"eval_loss": 0.49, "eval_accuracy": 0.78, "num-examples": 90}
    )


def test_shared_payload_rejects_local_identifiers() -> None:
    for prohibited in ("client_id", "real_order_id", "uti", "live_intention", "hash_id"):
        with pytest.raises(ValueError, match="prohibited"):
            validate_shared_payload({"pair": "EUR/USD", prohibited: "secret"})
