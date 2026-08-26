"""Local XGBoost training and comparison for AgentApp (standalone, no connector dependency)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb

from .domain import ProviderEvidence

# Feature names from federation data module
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
class ModelComparison:
    pair: str
    provider: str
    federated_fill_prob: float
    xgboost_fill_prob: float
    federated_slippage_bps: float
    xgboost_slippage_bps: float
    federated_latency_ms: float
    xgboost_latency_ms: float
    xgboost_feature_importance: dict[str, float]
    model_agreement: bool


def _train_local_xgb_models() -> tuple[xgb.Booster, xgb.Booster, xgb.Booster]:
    """Train local XGBoost models on synthetic data matching federation features."""
    rng = np.random.default_rng(20260826)
    n_samples = 2000
    
    # Features: provider, high_vol, size, quote_age
    provider = rng.choice(3, n_samples, p=[0.4, 0.35, 0.25])
    high_vol = rng.binomial(1, 0.3, n_samples)
    size_scaled = rng.uniform(0.05, 1.0, n_samples)
    quote_age_scaled = rng.uniform(0.0, 1.0, n_samples)
    one_hot = np.eye(3, dtype=np.float64)[provider]
    
    X_full = np.column_stack([
        one_hot,
        high_vol,
        one_hot[:, 0] * high_vol,
        one_hot[:, 2] * high_vol,
        size_scaled,
        quote_age_scaled,
    ])
    
    # Targets
    logits = (
        1.25 - 0.30 * one_hot[:, 0] + 0.38 * one_hot[:, 1] + 0.02 * one_hot[:, 2]
        - 0.80 * high_vol - 1.05 * one_hot[:, 0] * high_vol - 0.62 * one_hot[:, 2] * high_vol
        - 0.35 * size_scaled - 0.40 * quote_age_scaled
    )
    y_fill = rng.binomial(1, 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30))))
    
    y_slippage = 1.10 * one_hot[:, 0] + 0.42 * one_hot[:, 1] + 0.84 * one_hot[:, 2]
    y_slippage += 0.5 * high_vol + rng.normal(0, 0.1, n_samples)
    
    y_latency = 78.0 * one_hot[:, 0] + 31.0 * one_hot[:, 1] + 86.0 * one_hot[:, 2]
    y_latency += 20.0 * high_vol + rng.normal(0, 5.0, n_samples)
    
    dtrain_fill = xgb.DMatrix(X_full, label=y_fill, feature_names=FEATURE_NAMES)
    dtrain_slip = xgb.DMatrix(X_full, label=y_slippage, feature_names=FEATURE_NAMES)
    dtrain_lat = xgb.DMatrix(X_full, label=y_latency, feature_names=FEATURE_NAMES)
    
    fill_params = {"objective": "binary:logistic", "max_depth": 4, "eta": 0.1, "seed": 20260826, "verbosity": 0}
    reg_params = {"objective": "reg:squarederror", "max_depth": 4, "eta": 0.1, "seed": 20260826, "verbosity": 0}
    
    fill_model = xgb.train(fill_params, dtrain_fill, num_boost_round=50)
    slippage_model = xgb.train(reg_params, dtrain_slip, num_boost_round=50)
    latency_model = xgb.train(reg_params, dtrain_lat, num_boost_round=50)
    
    return fill_model, slippage_model, latency_model


def train_local_xgboost_models() -> tuple[xgb.Booster, xgb.Booster, xgb.Booster]:
    """Train and return local XGBoost models (fill, slippage, latency)."""
    # Try to load from artifact first
    model_dir = Path(__file__).parent / "artifacts" / "xgboost_models"
    if (model_dir / "fill_model.json").exists():
        fill_model = xgb.Booster()
        fill_model.load_model(str(model_dir / "fill_model.json"))
        slippage_model = xgb.Booster()
        slippage_model.load_model(str(model_dir / "slippage_model.json"))
        latency_model = xgb.Booster()
        latency_model.load_model(str(model_dir / "latency_model.json"))
        return fill_model, slippage_model, latency_model
    
    return _train_local_xgb_models()


def compare_models(
    pair: str,
    providers: list[str],
    evidence: list[ProviderEvidence],
    fill_model: xgb.Booster,
    slippage_model: xgb.Booster,
    latency_model: xgb.Booster,
) -> list[ModelComparison]:
    """Compare local XGBoost predictions vs federated logistic evidence."""
    comparisons = []
    for provider in providers:
        fed = next((e for e in evidence if e.provider == provider), None)
        if not fed:
            continue
        
        # Build feature vector
        is_lp_a = 1.0 if provider == "LP_A" else 0.0
        is_lp_b = 1.0 if provider == "LP_B" else 0.0
        is_lp_c = 1.0 if provider == "LP_C" else 0.0
        high_vol = 0.3
        size_scaled = 0.5
        quote_age_scaled = 0.3
        
        X = np.array([[
            is_lp_a, is_lp_b, is_lp_c, high_vol,
            is_lp_a * high_vol, is_lp_c * high_vol,
            size_scaled, quote_age_scaled
        ]])
        dmatrix = xgb.DMatrix(X, feature_names=FEATURE_NAMES)
        
        xgb_fill = float(fill_model.predict(dmatrix)[0])
        xgb_slippage = float(slippage_model.predict(dmatrix)[0])
        xgb_latency = float(latency_model.predict(dmatrix)[0])
        
        importance = fill_model.get_score(importance_type="gain")
        full_importance = {name: importance.get(name, 0.0) for name in FEATURE_NAMES}
        
        model_agreement = (xgb_fill > 0.5) == (fed.fill_probability > 0.5)
        
        comparisons.append(ModelComparison(
            pair=pair,
            provider=provider,
            federated_fill_prob=fed.fill_probability,
            xgboost_fill_prob=xgb_fill,
            federated_slippage_bps=fed.expected_slippage_bps,
            xgboost_slippage_bps=xgb_slippage,
            federated_latency_ms=fed.expected_latency_ms,
            xgboost_latency_ms=xgb_latency,
            xgboost_feature_importance=full_importance,
            model_agreement=model_agreement,
        ))
    
    return comparisons