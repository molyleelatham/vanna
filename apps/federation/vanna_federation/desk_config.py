"""Desk configuration for parameterized synthetic data generation.

Each desk gets a config that defines its execution behavior.
Configs can be loaded from a local file or fetched from an API endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json
from pathlib import Path


@dataclass(frozen=True)
class DeskConfig:
    """Configuration for a single desk's synthetic execution behavior."""
    desk_id: str
    partition_id: int
    
    # Provider mix (must sum to 1.0)
    provider_probs: tuple[float, float, float] = (0.42, 0.34, 0.24)
    
    # Base volatility probability
    base_volatility_prob: float = 0.30
    volatility_increment_per_desk: float = 0.025
    
    # Logit coefficients (execution behavior)
    base_logit: float = 1.25
    lp_a_coeff: float = -0.30
    lp_b_coeff: float = 0.38
    lp_c_coeff: float = 0.02
    volatility_coeff: float = -0.80
    lp_a_vol_interaction: float = -1.05
    lp_c_vol_interaction: float = -0.62
    size_coeff: float = -0.35
    quote_age_coeff: float = -0.40
    noise_std: float = 0.12
    
    # Derived: desk-specific volatility prob
    @property
    def volatility_prob(self) -> float:
        return self.base_volatility_prob + self.partition_id * self.volatility_increment_per_desk
    
    # Derived: desk-specific provider probs (rotated)
    @property
    def rotated_provider_probs(self) -> tuple[float, float, float]:
        probs = list(self.provider_probs)
        n = self.partition_id % 3
        return tuple(probs[n:] + probs[:n])
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "desk_id": self.desk_id,
            "partition_id": self.partition_id,
            "provider_probs": list(self.provider_probs),
            "base_volatility_prob": self.base_volatility_prob,
            "volatility_increment_per_desk": self.volatility_increment_per_desk,
            "base_logit": self.base_logit,
            "lp_a_coeff": self.lp_a_coeff,
            "lp_b_coeff": self.lp_b_coeff,
            "lp_c_coeff": self.lp_c_coeff,
            "volatility_coeff": self.volatility_coeff,
            "lp_a_vol_interaction": self.lp_a_vol_interaction,
            "lp_c_vol_interaction": self.lp_c_vol_interaction,
            "size_coeff": self.size_coeff,
            "quote_age_coeff": self.quote_age_coeff,
            "noise_std": self.noise_std,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeskConfig":
        return cls(
            desk_id=data["desk_id"],
            partition_id=data["partition_id"],
            provider_probs=tuple(data["provider_probs"]),
            base_volatility_prob=data.get("base_volatility_prob", 0.30),
            volatility_increment_per_desk=data.get("volatility_increment_per_desk", 0.025),
            base_logit=data.get("base_logit", 1.25),
            lp_a_coeff=data.get("lp_a_coeff", -0.30),
            lp_b_coeff=data.get("lp_b_coeff", 0.38),
            lp_c_coeff=data.get("lp_c_coeff", 0.02),
            volatility_coeff=data.get("volatility_coeff", -0.80),
            lp_a_vol_interaction=data.get("lp_a_vol_interaction", -1.05),
            lp_c_vol_interaction=data.get("lp_c_vol_interaction", -0.62),
            size_coeff=data.get("size_coeff", -0.35),
            quote_age_coeff=data.get("quote_age_coeff", -0.40),
            noise_std=data.get("noise_std", 0.12),
        )


DEFAULT_DESK_CONFIGS = [
    DeskConfig(desk_id="DESK_A", partition_id=0),
    DeskConfig(desk_id="DESK_B", partition_id=1),
    DeskConfig(desk_id="DESK_C", partition_id=2),
    DeskConfig(desk_id="DESK_D", partition_id=3),
    DeskConfig(desk_id="DESK_E", partition_id=4),
]


def load_desk_configs(path: Path | None = None) -> list[DeskConfig]:
    """Load desk configs from JSON file, or return defaults."""
    if path and path.exists():
        with path.open() as f:
            data = json.load(f)
        return [DeskConfig.from_dict(d) for d in data]
    return DEFAULT_DESK_CONFIGS


def save_desk_configs(configs: list[DeskConfig], path: Path) -> None:
    """Save desk configs to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump([c.to_dict() for c in configs], f, indent=2)


async def fetch_desk_configs_from_api(
    endpoint: str,
    api_key: str | None = None,
) -> list[DeskConfig]:
    """Fetch desk configs from an API endpoint.
    
    Expected API response format:
    {
        "desks": [
            {"desk_id": "DESK_A", "partition_id": 0, "provider_probs": [...], ...},
            ...
        ]
    }
    """
    import httpx
    
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(endpoint, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [DeskConfig.from_dict(d) for d in data.get("desks", [])]


def generate_random_desk_configs(num_desks: int = 5, seed: int = 42) -> list[DeskConfig]:
    """Generate randomized but reproducible desk configs for experimentation."""
    import numpy as np
    rng = np.random.default_rng(seed)
    
    configs = []
    for i in range(num_desks):
        # Randomize coefficients within sensible bounds
        config = DeskConfig(
            desk_id=f"DESK_{chr(65+i)}",  # DESK_A, DESK_B, ...
            partition_id=i,
            provider_probs=tuple(rng.dirichlet([2, 2, 1])),  # random but sums to 1
            base_volatility_prob=0.25 + rng.random() * 0.15,  # 0.25-0.40
            volatility_increment_per_desk=0.01 + rng.random() * 0.04,  # 0.01-0.05
            base_logit=1.0 + rng.random() * 0.5,  # 1.0-1.5
            lp_a_coeff=-0.5 + rng.random() * 0.4,  # -0.5 to -0.1
            lp_b_coeff=0.2 + rng.random() * 0.4,  # 0.2-0.6
            lp_c_coeff=-0.1 + rng.random() * 0.3,  # -0.1 to 0.2
            volatility_coeff=-1.2 + rng.random() * 0.6,  # -1.2 to -0.6
            lp_a_vol_interaction=-1.5 + rng.random() * 0.8,  # -1.5 to -0.7
            lp_c_vol_interaction=-1.0 + rng.random() * 0.6,  # -1.0 to -0.4
            size_coeff=-0.5 + rng.random() * 0.3,  # -0.5 to -0.2
            quote_age_coeff=-0.6 + rng.random() * 0.3,  # -0.6 to -0.3
            noise_std=0.08 + rng.random() * 0.08,  # 0.08-0.16
        )
        configs.append(config)
    return configs