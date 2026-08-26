"""Genuine local-only vs federated comparison for the AgentApp.

The "local" model is trained on ONE desk's persisted partition (desk 0) — what
a single desk would know alone. The "federated" model is the final ensemble
produced by the five-desk federation. Both are evaluated on the desk's
held-out test split, so the comparison measures the actual value of
collaboration instead of restating the constants the evidence was built from.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xgboost as xgb

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

ARTIFACTS = Path(__file__).parent / "artifacts"
FEDERATED_MODEL_PATH = ARTIFACTS / "federated_final_model.json"
LOCAL_DESK_PATH = ARTIFACTS / "local_desk_0.json"

# Same LP feature vectors the federation uses for evidence export (high vol).
LP_FEATURES = np.array(
    [
        [1, 0, 0, 1, 1, 0, 0.4, 0.25],  # LP_A
        [0, 1, 0, 1, 0, 0, 0.4, 0.25],  # LP_B
        [0, 0, 1, 1, 0, 1, 0.4, 0.25],  # LP_C
    ],
    dtype=np.float64,
)

LOCAL_TRAIN_PARAMS = {
    "objective": "binary:logistic",
    "max_depth": 4,
    "eta": 0.1,
    "seed": 20260826,
    "verbosity": 0,
}


@dataclass(frozen=True)
class ModelComparison:
    pair: str
    provider: str
    federated_fill_prob: float
    local_only_fill_prob: float
    federated_logloss_held_out: float
    local_only_logloss_held_out: float
    model_agreement: bool
    federated_feature_importance: dict[str, float]


def _logloss(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    eps = 1e-8
    clipped = np.clip(y_pred, eps, 1 - eps)
    return float(-np.mean(y_true * np.log(clipped) + (1 - y_true) * np.log(1 - clipped)))


def _load_federated_model(path: Path = FEDERATED_MODEL_PATH) -> xgb.Booster:
    if not path.exists():
        raise FileNotFoundError(
            f"federated ensemble missing at {path}; run scripts/sync_federation_artifact.py"
        )
    model = xgb.Booster()
    model.load_model(bytearray(path.read_bytes()))
    return model


def _train_local_only_model(path: Path = LOCAL_DESK_PATH) -> tuple[xgb.Booster, np.ndarray, np.ndarray]:
    """Train on one desk's partition only; return the model and its held-out split."""
    if not path.exists():
        raise FileNotFoundError(
            f"local desk partition missing at {path}; run scripts/sync_federation_artifact.py"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    x_train = np.asarray(data["x_train"], dtype=np.float64)
    y_train = np.asarray(data["y_train"], dtype=np.float64)
    x_test = np.asarray(data["x_test"], dtype=np.float64)
    y_test = np.asarray(data["y_test"], dtype=np.float64)
    dtrain = xgb.DMatrix(x_train, label=y_train, feature_names=FEATURE_NAMES)
    model = xgb.train(LOCAL_TRAIN_PARAMS, dtrain, num_boost_round=50)
    return model, x_test, y_test


def build_model_comparison(pair: str, providers: list[str]) -> list[ModelComparison]:
    """Compare the federated ensemble against a single-desk model, held out."""
    federated = _load_federated_model()
    local_model, x_test, y_test = _train_local_only_model()

    importance = federated.get_score(importance_type="gain")
    full_importance = {name: float(importance.get(name, 0.0)) for name in FEATURE_NAMES}

    fed_test_preds = federated.predict(xgb.DMatrix(x_test, feature_names=FEATURE_NAMES))
    local_test_preds = local_model.predict(xgb.DMatrix(x_test, feature_names=FEATURE_NAMES))

    provider_columns = {"LP_A": 0, "LP_B": 1, "LP_C": 2}
    comparisons: list[ModelComparison] = []
    for provider in providers:
        col = provider_columns.get(provider)
        if col is None:
            continue

        row = LP_FEATURES[col : col + 1]
        fed_fill = float(federated.predict(xgb.DMatrix(row, feature_names=FEATURE_NAMES))[0])
        local_fill = float(local_model.predict(xgb.DMatrix(row, feature_names=FEATURE_NAMES))[0])

        # Per-provider held-out loss on the desk's test split
        mask = x_test[:, col] == 1.0
        if mask.sum() >= 5:
            fed_loss = _logloss(y_test[mask], fed_test_preds[mask])
            local_loss = _logloss(y_test[mask], local_test_preds[mask])
        else:
            fed_loss = local_loss = float("nan")

        comparisons.append(
            ModelComparison(
                pair=pair,
                provider=provider,
                federated_fill_prob=round(fed_fill, 6),
                local_only_fill_prob=round(local_fill, 6),
                federated_logloss_held_out=round(fed_loss, 4),
                local_only_logloss_held_out=round(local_loss, 4),
                model_agreement=(fed_fill > 0.5) == (local_fill > 0.5),
                federated_feature_importance=full_importance,
            )
        )
    return comparisons
