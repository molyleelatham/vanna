"""Local XGBoost model for fill/slippage/rejection prediction (client-side benchmark)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb
from numpy.typing import NDArray

from .data import FEATURE_NAMES

XGB_PARAMS = {
    "objective": "binary:logistic",
    "max_depth": 4,
    "eta": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "eval_metric": "logloss",
    "seed": 20260826,
    "verbosity": 0,
}

NUM_BOOST_ROUND = 50


def train_xgboost(
    x_train: NDArray[np.float64],
    y_train: NDArray[np.float64],
    params: dict[str, Any] | None = None,
    num_boost_round: int = NUM_BOOST_ROUND,
) -> xgb.Booster:
    """Train local XGBoost model on desk data."""
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=FEATURE_NAMES)
    model = xgb.train(params or XGB_PARAMS, dtrain, num_boost_round=num_boost_round)
    return model


def predict_xgboost(
    model: xgb.Booster,
    x: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Predict fill probability using XGBoost model."""
    dmatrix = xgb.DMatrix(x, feature_names=FEATURE_NAMES)
    return model.predict(dmatrix)


def evaluate_xgboost(
    model: xgb.Booster,
    x_test: NDArray[np.float64],
    y_test: NDArray[np.float64],
) -> dict[str, float]:
    """Evaluate XGBoost model on test data."""
    preds = predict_xgboost(model, x_test)
    pred_labels = (preds >= 0.5).astype(np.float64)
    accuracy = float(np.mean(pred_labels == y_test))
    logloss = float(-np.mean(y_test * np.log(np.clip(preds, 1e-8, 1 - 1e-8))
                            + (1 - y_test) * np.log(np.clip(1 - preds, 1e-8, 1 - 1e-8))))
    return {
        "accuracy": accuracy,
        "logloss": logloss,
        "fill_rate_pred": float(np.mean(preds)),
        "fill_rate_actual": float(np.mean(y_test)),
    }


def get_feature_importance(model: xgb.Booster) -> dict[str, float]:
    """Get feature importance from XGBoost model (gain-based)."""
    importance = model.get_score(importance_type="gain")
    # Ensure all features present
    full = {name: importance.get(name, 0.0) for name in FEATURE_NAMES}
    return full


def model_to_json(model: xgb.Booster) -> str:
    """Serialize XGBoost model to JSON string."""
    return model.save_config()


def model_from_json(json_str: str) -> xgb.Booster:
    """Deserialize XGBoost model from JSON string."""
    model = xgb.Booster()
    model.load_config(json_str)
    return model


def save_model(model: xgb.Booster, path: Path) -> None:
    """Save XGBoost model to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))


def load_model(path: Path) -> xgb.Booster:
    """Load XGBoost model from file."""
    model = xgb.Booster()
    model.load_model(str(path))
    return model


# Multi-target models for slippage & rejection risk
def train_xgboost_regression(
    x_train: NDArray[np.float64],
    y_train: NDArray[np.float64],
    params: dict[str, Any] | None = None,
    num_boost_round: int = NUM_BOOST_ROUND,
) -> xgb.Booster:
    """Train XGBoost regression model (for slippage/latency)."""
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=FEATURE_NAMES)
    reg_params = params or {
        "objective": "reg:squarederror",
        "max_depth": 4,
        "eta": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "eval_metric": "rmse",
        "seed": 20260826,
        "verbosity": 0,
    }
    model = xgb.train(reg_params, dtrain, num_boost_round=num_boost_round)
    return model


def predict_xgboost_regression(
    model: xgb.Booster,
    x: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Predict continuous target (slippage, latency)."""
    dmatrix = xgb.DMatrix(x, feature_names=FEATURE_NAMES)
    return model.predict(dmatrix)