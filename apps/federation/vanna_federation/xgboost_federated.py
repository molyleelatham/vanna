"""Federated XGBoost model using Flower's FedXgbBagging strategy.

Each client trains local XGBoost trees; server aggregates via bagging (concatenation).
Model grows by M trees per round (M = num_clients).
"""

from __future__ import annotations

import io
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
    "tree_method": "hist",
    "nthread": 1,
}

# Regression params for slippage/latency
XGB_REG_PARAMS = {
    "objective": "reg:squarederror",
    "max_depth": 4,
    "eta": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "eval_metric": "rmse",
    "seed": 20260826,
    "verbosity": 0,
    "tree_method": "hist",
    "nthread": 1,
}

NUM_LOCAL_TREES = 1  # trees per client per round
NUM_BOOST_ROUND = 1  # local-epochs equivalent


def _logloss(y_true: NDArray[np.float64], y_pred: NDArray[np.float64]) -> float:
    """Compute binary log loss."""
    eps = 1e-8
    clipped_preds = np.clip(y_pred, eps, 1 - eps)
    clipped_1mpreds = np.clip(1 - y_pred, eps, 1 - eps)
    loss = -np.mean(
        y_true * np.log(clipped_preds)
        + (1 - y_true) * np.log(clipped_1mpreds)
    )
    return float(loss)


def initial_xgb_model() -> bytes:
    """Create initial XGBoost model trained on representative data."""
    model = xgb.Booster(params=XGB_PARAMS)
    # Train on small representative dataset to initialize properly
    rng = np.random.default_rng(20260826)
    n_init = 500
    provider = rng.choice(3, n_init, p=[0.4, 0.35, 0.25])
    high_vol = rng.binomial(1, 0.3, n_init)
    size_scaled = rng.uniform(0.05, 1.0, n_init)
    quote_age = rng.uniform(0.0, 1.0, n_init)
    one_hot = np.eye(3, dtype=np.float64)[provider]
    
    X = np.column_stack([
        one_hot,
        high_vol,
        one_hot[:, 0] * high_vol,
        one_hot[:, 2] * high_vol,
        size_scaled,
        quote_age,
    ])
    logits = (
        1.25 - 0.30 * one_hot[:, 0] + 0.38 * one_hot[:, 1] + 0.02 * one_hot[:, 2]
        - 0.80 * high_vol - 1.05 * one_hot[:, 0] * high_vol - 0.62 * one_hot[:, 2] * high_vol
        - 0.35 * size_scaled - 0.40 * quote_age
    )
    y = rng.binomial(1, 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30))))
    
    dtrain = xgb.DMatrix(X, label=y, feature_names=FEATURE_NAMES)
    model = xgb.train(XGB_PARAMS, dtrain, num_boost_round=10)
    return model.save_raw("json")


def xgb_model_to_bytes(model: xgb.Booster) -> bytes:
    """Serialize XGBoost model to bytes (JSON format)."""
    return model.save_raw("json")


def bytes_to_xgb_model(raw: bytes, params: dict | None = None) -> xgb.Booster:
    """Deserialize bytes to XGBoost model."""
    model = xgb.Booster(params=params or XGB_PARAMS)
    model.load_model(bytearray(raw))
    return model


def train_xgboost_local(
    x_train: NDArray[np.float64],
    y_train: NDArray[np.float64],
    global_model_bytes: bytes,
    num_local_trees: int = NUM_LOCAL_TREES,
) -> tuple[bytes, float]:
    """Train local XGBoost model starting from global model.
    
    Returns updated model bytes and training loss.
    """
    # Load global model
    global_model = bytes_to_xgb_model(global_model_bytes)
    
    # Create DMatrix
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=FEATURE_NAMES)
    
    # Continue training from global model
    # XGBoost will add `num_local_trees` to the existing ensemble
    updated_model = xgb.train(
        XGB_PARAMS,
        dtrain,
        num_boost_round=num_local_trees,
        xgb_model=global_model,
    )
    
    # Calculate training loss
    preds = updated_model.predict(dtrain)
    loss = _logloss(y_train, preds)
    
    return xgb_model_to_bytes(updated_model), loss


def evaluate_xgboost(
    model_bytes: bytes,
    x_test: NDArray[np.float64],
    y_test: NDArray[np.float64],
) -> dict[str, float]:
    """Evaluate XGBoost model on test data."""
    model = bytes_to_xgb_model(model_bytes)
    dtest = xgb.DMatrix(x_test, label=y_test, feature_names=FEATURE_NAMES)
    preds = model.predict(dtest)
    
    pred_labels = (preds >= 0.5).astype(np.float64)
    accuracy = float(np.mean(pred_labels == y_test))
    logloss = _logloss(y_test, preds)
    
    return {
        "accuracy": accuracy,
        "logloss": logloss,
        "fill_rate_pred": float(np.mean(preds)),
        "fill_rate_actual": float(np.mean(y_test)),
    }


def get_feature_importance(model_bytes: bytes) -> dict[str, float]:
    """Get feature importance from XGBoost model."""
    model = bytes_to_xgb_model(model_bytes)
    importance = model.get_score(importance_type="gain")
    return {name: importance.get(name, 0.0) for name in FEATURE_NAMES}


def predict_xgboost(model_bytes: bytes, x: NDArray[np.float64]) -> NDArray[np.float64]:
    """Predict fill probability using XGBoost model."""
    model = bytes_to_xgb_model(model_bytes)
    dmatrix = xgb.DMatrix(x, feature_names=FEATURE_NAMES)
    return model.predict(dmatrix)


def save_model(model_bytes: bytes, path: Path) -> None:
    """Save XGBoost model bytes to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(model_bytes)


def load_model(path: Path) -> bytes:
    """Load XGBoost model bytes from file."""
    return path.read_bytes()


# Multi-target regression models (slippage, latency, rejection probability)
def train_xgboost_regression(
    x_train: NDArray[np.float64],
    y_train: NDArray[np.float64],
    global_model_bytes: bytes | None = None,
    num_local_trees: int = NUM_LOCAL_TREES,
) -> tuple[bytes, float]:
    """Train local XGBoost regression model starting from global model."""
    if global_model_bytes:
        global_model = bytes_to_xgb_model(global_model_bytes)
    else:
        global_model = xgb.Booster(params=XGB_REG_PARAMS)
    
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=FEATURE_NAMES)
    updated_model = xgb.train(
        XGB_REG_PARAMS,
        dtrain,
        num_boost_round=num_local_trees,
        xgb_model=global_model,
    )
    preds = updated_model.predict(dtrain)
    loss = float(np.mean((preds - y_train) ** 2))
    return xgb_model_to_bytes(updated_model), loss


def predict_xgboost_regression(
    model_bytes: bytes,
    x: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Predict continuous target (slippage, latency, rejection prob)."""
    model = bytes_to_xgb_model(model_bytes, params=XGB_REG_PARAMS)
    dmatrix = xgb.DMatrix(x, feature_names=FEATURE_NAMES)
    return model.predict(dmatrix)


def train_local_regression_models(
    x_train: NDArray[np.float64],
    y_slippage: NDArray[np.float64],
    y_latency: NDArray[np.float64],
    y_rejection: NDArray[np.float64],
) -> tuple[bytes, bytes, bytes]:
    """Train local regression models for slippage, latency, rejection probability."""
    dtrain_slip = xgb.DMatrix(x_train, label=y_slippage, feature_names=FEATURE_NAMES)
    dtrain_lat = xgb.DMatrix(x_train, label=y_latency, feature_names=FEATURE_NAMES)
    dtrain_rej = xgb.DMatrix(x_train, label=y_rejection, feature_names=FEATURE_NAMES)
    
    # Create fresh boosters with regression params (not binary logistic)
    slip_model = xgb.train(XGB_REG_PARAMS, dtrain_slip, num_boost_round=50)
    lat_model = xgb.train(XGB_REG_PARAMS, dtrain_lat, num_boost_round=50)
    rej_model = xgb.train(XGB_REG_PARAMS, dtrain_rej, num_boost_round=50)
    
    return (
        xgb_model_to_bytes(slip_model),
        xgb_model_to_bytes(lat_model),
        xgb_model_to_bytes(rej_model),
    )