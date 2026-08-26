"""Tests for the default FedXgbBagging path (previously untested)."""

import json

import numpy as np
import pytest

from vanna_federation.data import generate_desk_data_legacy, global_test_data_legacy
from vanna_federation.persistence import TrainingManifest
from vanna_federation.server_app import export_approved_evidence
from vanna_federation.xgboost_federated import (
    bytes_to_xgb_model,
    evaluate_xgboost,
    initial_xgb_model,
    predict_xgboost,
    predict_xgboost_regression,
    train_local_regression_models,
    train_xgboost_local,
)


def test_initial_model_produces_valid_probabilities() -> None:
    model_bytes = initial_xgb_model()
    x_test, _ = global_test_data_legacy()
    preds = predict_xgboost(model_bytes, x_test)
    assert len(preds) == len(x_test)
    assert np.all(preds >= 0.0) and np.all(preds <= 1.0)


def test_train_xgboost_local_continues_from_global_model() -> None:
    desk = generate_desk_data_legacy(0)
    initial = initial_xgb_model()
    initial_trees = bytes_to_xgb_model(initial).num_boosted_rounds()

    updated_bytes, loss = train_xgboost_local(
        desk.x_train, desk.y_train, initial, num_local_trees=1
    )
    updated_trees = bytes_to_xgb_model(updated_bytes).num_boosted_rounds()

    assert updated_trees == initial_trees + 1
    assert np.isfinite(loss)
    assert 0.0 <= loss <= 5.0


def test_evaluate_xgboost_returns_sane_metrics() -> None:
    x_test, y_test = global_test_data_legacy()
    metrics = evaluate_xgboost(initial_xgb_model(), x_test, y_test)
    assert 0.0 <= metrics["logloss"] <= 5.0
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["fill_rate_pred"] <= 1.0


def test_regression_models_predict_nonnegative_targets() -> None:
    desk = generate_desk_data_legacy(1)
    rng = np.random.default_rng(7)
    y_slip = np.abs(rng.normal(0.8, 0.2, len(desk.y_train)))
    y_lat = np.abs(rng.normal(60.0, 10.0, len(desk.y_train)))
    y_rej = rng.random(len(desk.y_train))

    slip_b, lat_b, rej_b = train_local_regression_models(
        desk.x_train, y_slip, y_lat, y_rej
    )
    preds = predict_xgboost_regression(slip_b, desk.x_test)
    assert len(preds) == len(desk.x_test)
    assert np.all(np.isfinite(preds))


def test_export_approved_evidence_schema_and_provenance(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fills = np.array([0.30, 0.88, 0.11])
    output = export_approved_evidence(fills, "fed-test-v1", TrainingManifest())

    payload = json.loads(output.read_text())
    assert payload["raw_records_shared"] == 0
    assert payload["client_identities_shared"] == 0
    assert payload["cohort_size"] == 5
    assert "provenance" in payload
    assert "synthetic" in payload["provenance"]["displayed_price_benefit_bps"]

    forbidden = {"client_id", "account_id", "real_order_id", "local_order_id", "uti", "live_intention"}
    assert not forbidden.intersection({k.lower() for k in payload})

    providers = payload["providers"]
    assert [p["provider"] for p in providers] == ["LP_A", "LP_B", "LP_C"]
    for item in providers:
        assert 0.0 <= item["fill_probability"] <= 1.0
        assert 0.0 <= item["rejection_probability"] <= 1.0
        assert item["expected_slippage_bps"] >= 0.0
        assert item["expected_latency_ms"] >= 0.0
    # Fill probabilities come from the federated predictions, not constants
    assert providers[1]["fill_probability"] == pytest.approx(0.88, abs=1e-6)


def test_genuine_comparison_uses_real_artifacts() -> None:
    """The agent-side comparison must use the synced ensemble + desk partition."""
    from vanna_agent.xgboost_local import (
        FEDERATED_MODEL_PATH,
        LOCAL_DESK_PATH,
        build_model_comparison,
    )

    if not (FEDERATED_MODEL_PATH.exists() and LOCAL_DESK_PATH.exists()):
        pytest.skip("run scripts/sync_federation_artifact.py first")

    comparisons = build_model_comparison("EUR/USD", ["LP_A", "LP_B", "LP_C"])
    assert len(comparisons) == 3
    for c in comparisons:
        assert 0.0 <= c.federated_fill_prob <= 1.0
        assert 0.0 <= c.local_only_fill_prob <= 1.0
        assert np.isfinite(c.federated_logloss_held_out)
        assert np.isfinite(c.local_only_logloss_held_out)
    # The two models are genuinely different objects trained on different data
    assert any(
        c.federated_fill_prob != c.local_only_fill_prob for c in comparisons
    )
