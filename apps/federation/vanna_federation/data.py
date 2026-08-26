"""Reproducible synthetic FX histories for five isolated desks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

PROVIDERS = ("LP_A", "LP_B", "LP_C")
FEATURE_NAMES = (
    "is_lp_a",
    "is_lp_b",
    "is_lp_c",
    "is_high_volatility",
    "is_lp_a_high_volatility",
    "is_lp_c_high_volatility",
    "size_scaled",
    "quote_age_scaled",
)


@dataclass(frozen=True)
class DeskData:
    x_train: NDArray[np.float64]
    y_train: NDArray[np.float64]
    x_test: NDArray[np.float64]
    y_test: NDArray[np.float64]


def _sigmoid(value: NDArray[np.float64]) -> NDArray[np.float64]:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30, 30)))


def generate_desk_data(partition_id: int, samples: int = 450) -> DeskData:
    """Generate one private partition with a desk-specific observation bias."""
    if not 0 <= partition_id < 5:
        raise ValueError("partition_id must identify one of five desks")
    rng = np.random.default_rng(20260826 + partition_id)
    provider = rng.choice(3, size=samples, p=np.roll([0.42, 0.34, 0.24], partition_id % 3))
    high_volatility = rng.binomial(1, 0.30 + partition_id * 0.025, samples)
    size_scaled = rng.uniform(0.05, 1.0, samples)
    quote_age_scaled = rng.uniform(0.0, 1.0, samples)
    one_hot = np.eye(3, dtype=np.float64)[provider]
    x = np.column_stack(
        (
            one_hot,
            high_volatility,
            one_hot[:, 0] * high_volatility,
            one_hot[:, 2] * high_volatility,
            size_scaled,
            quote_age_scaled,
        )
    )

    # LP_A looks cheapest but becomes unreliable in fast markets. LP_B is stable.
    logits = (
        1.25
        - 0.30 * one_hot[:, 0]
        + 0.38 * one_hot[:, 1]
        + 0.02 * one_hot[:, 2]
        - 0.80 * high_volatility
        - 1.05 * one_hot[:, 0] * high_volatility
        - 0.62 * one_hot[:, 2] * high_volatility
        - 0.35 * size_scaled
        - 0.40 * quote_age_scaled
        + rng.normal(0, 0.12, samples)
    )
    y = rng.binomial(1, _sigmoid(logits)).astype(np.float64)
    split = int(samples * 0.8)
    return DeskData(x[:split], y[:split], x[split:], y[split:])


def global_test_data() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    partitions = [generate_desk_data(index) for index in range(5)]
    return (
        np.concatenate([partition.x_test for partition in partitions]),
        np.concatenate([partition.y_test for partition in partitions]),
    )
