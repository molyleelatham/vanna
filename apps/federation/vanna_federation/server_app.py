"""Flower server coordinating five desks and exporting approved evidence.

Uses FedXgbBagging strategy for federated XGBoost bagging aggregation.
Includes checkpointing, training manifest, and final ensemble persistence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedXgbBagging

from .data import FEATURE_NAMES, global_test_data_legacy
from .model import predict_probability
from .secagg import run_secure_federation
from .xgboost_federated import (
    initial_xgb_model,
    evaluate_xgboost,
    get_feature_importance,
    predict_xgboost,
    predict_xgboost_regression,
    train_local_regression_models,
    bytes_to_xgb_model,
)
from .persistence import (
    TrainingManifest,
    ensure_dirs,
    save_model_checkpoint,
    save_final_ensemble,
    save_feature_importance,
    save_provider_evidence,
    save_training_manifest,
    compute_model_digest,
)

app = ServerApp()


def global_evaluate(_server_round: int, arrays: ArrayRecord) -> MetricRecord:
    x_test, y_test = global_test_data_legacy()
    model_bytes = arrays.to_numpy_ndarrays()[0].tobytes()
    metrics_dict = evaluate_xgboost(model_bytes, x_test, y_test)
    return MetricRecord(
        {
            "centralized_loss": metrics_dict["logloss"],
            "centralized_accuracy": metrics_dict["accuracy"],
        }
    )


# Features for each LP used for evidence export (shared by both model paths)
LP_FEATURES = np.array(
    [
        [1, 0, 0, 1, 1, 0, 0.4, 0.25],  # LP_A high vol
        [0, 1, 0, 1, 0, 0, 0.4, 0.25],  # LP_B high vol
        [0, 0, 1, 1, 0, 1, 0.4, 0.25],  # LP_C high vol
    ],
    dtype=np.float64,
)


def export_approved_evidence(
    fill_probabilities: np.ndarray, model_tag: str, manifest: TrainingManifest
) -> Path:
    """Export provider evidence from federated fill-probability predictions.

    Derives slippage, latency, rejection prob from regression models
    trained on the same synthetic data (in production: from local models).
    """
    features = LP_FEATURES

    # Derive slippage, latency, rejection probability from regression models
    # (In production these come from local XGBoost regression models per desk)
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
    
    # Targets matching the original hardcoded profiles
    y_slippage = 1.10 * one_hot[:, 0] + 0.42 * one_hot[:, 1] + 0.84 * one_hot[:, 2]
    y_slippage += 0.5 * high_vol + rng.normal(0, 0.1, n_init)
    
    y_latency = 78.0 * one_hot[:, 0] + 31.0 * one_hot[:, 1] + 86.0 * one_hot[:, 2]
    y_latency += 20.0 * high_vol + rng.normal(0, 5.0, n_init)
    
    y_rejection = 0.70 * one_hot[:, 0] + 0.12 * one_hot[:, 1] + 0.89 * one_hot[:, 2]
    y_rejection += 0.1 * high_vol + rng.normal(0, 0.05, n_init)
    
    # Train local regression models
    slip_bytes, lat_bytes, rej_bytes = train_local_regression_models(X, y_slippage, y_latency, y_rejection)
    
    # Predict for each LP feature vector
    slippage_preds = predict_xgboost_regression(slip_bytes, features)
    latency_preds = predict_xgboost_regression(lat_bytes, features)
    rejection_preds = predict_xgboost_regression(rej_bytes, features)

    generated_at = datetime.now(UTC).isoformat()
    
    providers = []
    for index, provider in enumerate(["LP_A", "LP_B", "LP_C"]):
        fill_probability = float(fill_probabilities[index])
        slippage = float(slippage_preds[index])
        latency = float(latency_preds[index])
        rejection_prob = float(rejection_preds[index])
        # Clip rejection probability to [0, 1]
        rejection_prob = max(0.0, min(1.0, rejection_prob))
        providers.append(
            {
                "provider": provider,
                "sample_count": 450,
                "fill_probability": round(fill_probability, 6),
                "rejection_probability": round(rejection_prob, 6),
                "expected_slippage_bps": round(max(0.0, slippage), 2),
                "expected_latency_ms": round(max(0.0, latency), 1),
                "displayed_price_benefit_bps": 0.1 if provider == "LP_B" else (0.45 if provider == "LP_A" else 0.2),
                "rejection_asymmetry": 0.22 if provider == "LP_A" else (0.03 if provider == "LP_B" else 0.08),
                "model_version": model_tag,
                "generated_at": generated_at,
            }
        )
    evidence = {
        "cohort_size": 5,
        "raw_records_shared": 0,
        "client_identities_shared": 0,
        "provenance": {
            "fill_probability": "federated ensemble prediction from five desk partitions",
            "expected_slippage_bps": "XGBoost regression over synthetic desk-profile targets (demo stand-in for per-desk local regressions)",
            "expected_latency_ms": "XGBoost regression over synthetic desk-profile targets (demo stand-in for per-desk local regressions)",
            "rejection_probability": "XGBoost regression over synthetic desk-profile targets (demo stand-in for per-desk local regressions)",
            "displayed_price_benefit_bps": "synthetic desk-profile constant",
            "rejection_asymmetry": "synthetic desk-profile constant",
            "sample_count": "synthetic desk-profile constant",
        },
        "providers": providers,
    }
    output = Path("artifacts/generated/provider_evidence.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )
    
    # Save to persistence layer
    save_provider_evidence(evidence, manifest)
    return output


class CheckpointingFedXgbBagging(FedXgbBagging):
    """FedXgbBagging with automatic model checkpointing per round."""
    
    def __init__(self, manifest: TrainingManifest, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manifest = manifest
        self.round_num = 0
    
    def aggregate_fit(self, server_round: int, results, failures):
        self.round_num = server_round
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, results, failures
        )
        
        if aggregated_parameters is not None:
            # Extract model bytes from ArrayRecord
            try:
                model_bytes = aggregated_parameters.to_numpy_ndarrays()[0].tobytes()
                # Save checkpoint with metrics
                metrics = {
                    "train_loss": float(aggregated_metrics.get("train_loss", 0)),
                    "num_examples": int(aggregated_metrics.get("num-examples", 0)),
                }
                save_model_checkpoint(model_bytes, server_round, self.manifest, metrics)
            except Exception as e:
                print(f"Checkpoint save failed: {e}")
        
        return aggregated_parameters, aggregated_metrics


@app.main()
def main(grid: Grid, context: Context) -> None:
    # Initialize training manifest
    manifest = TrainingManifest()
    secure = bool(context.run_config["secure-aggregation"])
    manifest.config = {
        "num_desks": 5,
        "num_rounds": int(context.run_config["num-server-rounds"]),
        "local_trees": int(context.run_config["local-trees"]),
        "fraction_evaluate": float(context.run_config["fraction-evaluate"]),
        "secure_aggregation": "secaggplus" if secure else "none",
    }

    if secure:
        _main_secure(grid, context, manifest)
    else:
        _main_xgboost(grid, context, manifest)


def _main_secure(grid: Grid, context: Context, manifest: TrainingManifest) -> None:
    """FedAvg over the logistic model under SecAgg+ secure aggregation."""
    manifest.run_id = f"fed-logistic-secagg-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    final_params = run_secure_federation(grid, context, manifest)

    params_bytes = b"".join(
        np.asarray(array, dtype=np.float64).tobytes() for array in final_params
    )
    digest = compute_model_digest(params_bytes)
    save_final_ensemble(params_bytes, manifest)

    # The logistic weights are the transparent feature attribution
    weights = final_params[0]
    save_feature_importance(
        {name: round(float(weight), 6) for name, weight in zip(FEATURE_NAMES, weights)},
        manifest,
    )

    fill_probabilities = predict_probability(LP_FEATURES, final_params)
    output = export_approved_evidence(
        fill_probabilities, f"fed-logistic-secagg-{digest}", manifest
    )

    manifest.complete(
        final_model_path=str(Path("artifacts/final_ensemble/final_model.json")),
        feature_importance_path=str(Path("artifacts/generated/feature_importance.json")),
        evidence_path=str(output),
    )
    save_training_manifest(manifest)

    print(f"Approved aggregate evidence written to {output}")
    print("Raw orders shared: 0")
    print("Client identities shared: 0")
    print("Individual desk updates visible to server: 0 (SecAgg+ masked aggregation)")
    print("Training manifest saved to artifacts/training_manifest.json")
    print("Final model saved to artifacts/final_ensemble/final_model.json")
    print("Checkpoints saved to artifacts/checkpoints/")


def _main_xgboost(grid: Grid, context: Context, manifest: TrainingManifest) -> None:
    strategy = CheckpointingFedXgbBagging(
        manifest=manifest,
        fraction_train=1.0,
        fraction_evaluate=float(context.run_config["fraction-evaluate"]),
        min_train_nodes=5,
        min_evaluate_nodes=5,
        min_available_nodes=5,
    )
    
    # Run federated training with manual round-by-round checkpointing
    num_rounds = int(context.run_config["num-server-rounds"])
    
    # Create a simple loop to capture each round's model
    current_arrays = ArrayRecord([np.frombuffer(initial_xgb_model(), dtype=np.uint8)])
    train_config = ConfigRecord({"local-trees": int(context.run_config["local-trees"])})
    
    for round_num in range(1, num_rounds + 1):
        # Run one round
        round_result = strategy.start(
            grid=grid,
            initial_arrays=current_arrays,
            train_config=train_config,
            num_rounds=1,
            evaluate_fn=global_evaluate,
        )
        
        # Save checkpoint after this round
        round_arrays = round_result.arrays.to_numpy_ndarrays()
        if not round_arrays:
            # All nodes failed this round (e.g. missing deps); keep the last
            # known model and stop instead of crashing on an empty result.
            print(f"Round {round_num}: no client updates received; aborting early.")
            break
        round_model_bytes = round_arrays[0].tobytes()
        # Extract metrics from the result (check various possible locations)
        metrics = {"round": round_num}
        try:
            # Try centralized metrics
            if hasattr(round_result, 'metrics_centralized'):
                cent = round_result.metrics_centralized
                metrics.update({
                    "eval_loss": float(cent.get("centralized_loss", 0)),
                    "eval_accuracy": float(cent.get("centralized_accuracy", 0)),
                })
            # Try distributed metrics
            if hasattr(round_result, 'metrics_distributed'):
                dist = round_result.metrics_distributed
                if "train_loss" in dist:
                    # Get the latest round's value
                    latest_key = max(dist["train_loss"].keys())
                    metrics["train_loss"] = float(dist["train_loss"][latest_key])
                if "eval_loss" in dist:
                    latest_key = max(dist["eval_loss"].keys())
                    metrics["eval_loss"] = float(dist["eval_loss"][latest_key])
                if "eval_accuracy" in dist:
                    latest_key = max(dist["eval_accuracy"].keys())
                    metrics["eval_accuracy"] = float(dist["eval_accuracy"][latest_key])
        except Exception as e:
            print(f"Metrics extraction failed: {e}")
        
        save_model_checkpoint(round_model_bytes, round_num, manifest, metrics)
        
        # Update for next round
        current_arrays = round_result.arrays
    
    # Get final model after all rounds
    final_model_bytes = current_arrays.to_numpy_ndarrays()[0].tobytes()
    digest = compute_model_digest(final_model_bytes)
    
    # Save final ensemble
    save_final_ensemble(final_model_bytes, manifest)
    
    # Save feature importance
    importance = get_feature_importance(final_model_bytes)
    save_feature_importance(importance, manifest)

    # Export and save provider evidence
    fill_probabilities = predict_xgboost(final_model_bytes, LP_FEATURES)
    output = export_approved_evidence(fill_probabilities, f"fed-xgb-{digest}", manifest)
    
    # Complete and save manifest
    manifest.complete(
        final_model_path=str(Path("artifacts/final_ensemble/final_model.json")),
        feature_importance_path=str(Path("artifacts/generated/feature_importance.json")),
        evidence_path=str(output),
    )
    save_training_manifest(manifest)
    
    print(f"Approved aggregate evidence written to {output}")
    print("Raw orders shared: 0")
    print("Client identities shared: 0")
    print(f"Training manifest saved to artifacts/training_manifest.json")
    print(f"Final ensemble saved to artifacts/final_ensemble/final_model.json")
    print(f"Checkpoints saved to artifacts/checkpoints/")
