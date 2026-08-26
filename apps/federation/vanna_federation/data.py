"""Reproducible synthetic FX histories for isolated desks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .desk_config import DeskConfig, DEFAULT_DESK_CONFIGS

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


def generate_desk_data(
    config: DeskConfig,
    samples: int = 450,
) -> DeskData:
    """Generate one private partition from a DeskConfig."""
    rng = np.random.default_rng(20260826 + config.partition_id)
    
    # Provider mix (desk-specific, rotated)
    provider = rng.choice(3, size=samples, p=config.rotated_provider_probs)
    high_volatility = rng.binomial(1, config.volatility_prob, samples)
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

    # Desk-specific logit coefficients from config
    logits = (
        config.base_logit
        + config.lp_a_coeff * one_hot[:, 0]
        + config.lp_b_coeff * one_hot[:, 1]
        + config.lp_c_coeff * one_hot[:, 2]
        + config.volatility_coeff * high_volatility
        + config.lp_a_vol_interaction * one_hot[:, 0] * high_volatility
        + config.lp_c_vol_interaction * one_hot[:, 2] * high_volatility
        + config.size_coeff * size_scaled
        + config.quote_age_coeff * quote_age_scaled
        + rng.normal(0, config.noise_std, samples)
    )
    y = rng.binomial(1, _sigmoid(logits)).astype(np.float64)
    split = int(samples * 0.8)
    return DeskData(x[:split], y[:split], x[split:], y[split:])


def generate_all_desks(
    configs: list[DeskConfig] | None = None,
    samples: int = 450,
) -> list[DeskData]:
    """Generate data for all configured desks."""
    if configs is None:
        configs = DEFAULT_DESK_CONFIGS
    return [generate_desk_data(config, samples) for config in configs]


def global_test_data(configs: list[DeskConfig] | None = None) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Global test data from all desks."""
    desks = generate_all_desks(configs)
    return (
        np.concatenate([desk.x_test for desk in desks]),
        np.concatenate([desk.y_test for desk in desks]),
    )


# Backward compatibility
def generate_desk_data_legacy(partition_id: int, samples: int = 450) -> DeskData:
    """Legacy function for backward compatibility."""
    config = DEFAULT_DESK_CONFIGS[partition_id]
    return generate_desk_data(config, samples)


def global_test_data_legacy() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Legacy function for backward compatibility."""
    return global_test_data(DEFAULT_DESK_CONFIGS)