"""Desk-local privacy helpers. Kept inside the federation FAB (no vanna-core import)."""

from __future__ import annotations

import hashlib
import hmac

PROHIBITED_SHARED_FIELDS = frozenset(
    {
        "client_id",
        "account_id",
        "local_order_id",
        "real_order_id",
        "uti",
        "exact_notional",
        "exact_timestamp",
        "position",
        "live_intention",
        "hash_id",
        "secret",
        "vault",
    }
)


def pseudonymize(secret: str, local_order_id: str) -> str:
    if not secret or not local_order_id:
        raise ValueError("secret and local_order_id are required")
    return hmac.new(
        secret.encode("utf-8"),
        local_order_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def bucket_notional(notional: float) -> str:
    if notional < 0:
        raise ValueError("notional must be non-negative")
    if notional < 1_000_000:
        return "<1m"
    if notional < 5_000_000:
        return "1m-5m"
    if notional < 10_000_000:
        return "5m-10m"
    return ">10m"


def bucket_latency(latency_ms: float) -> str:
    if latency_ms < 0:
        raise ValueError("latency must be non-negative")
    if latency_ms < 25:
        return "fast"
    if latency_ms < 75:
        return "normal"
    return "slow"


def validate_shared_payload(payload: dict[str, object]) -> None:
    prohibited = PROHIBITED_SHARED_FIELDS.intersection(key.lower() for key in payload)
    if prohibited:
        raise ValueError(f"prohibited shared fields: {sorted(prohibited)}")
