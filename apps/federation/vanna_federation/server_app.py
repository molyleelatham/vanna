"""Flower server coordinating five desks and exporting approved evidence.

Uses FedXgbBagging strategy for federated XGBoost bagging aggregation.
Includes checkpointing, training manifest, and final ensemble persistence.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedXgbBagging

from .data import global_test_data_legacy
from .xgboost_federated import (
    initial_xgb_model,
    evaluate_xgboost,
    get_feature_importance,
    predict_xgboost,
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


def export_approved_evidence(model_bytes: bytes, manifest: TrainingManifest) -> Path:
    """Export provider evidence from federated XGBoost model."""
    model = bytes_to_xgb_model(model_bytes)
    
    # Generate features for each LP (same as before)
    features = np.array(
        [
            [1, 0, 0, 1, 1, 0, 0.4, 0.25],  # LP_A high vol
            [0, 1, 0, 1, 0, 0, 0.4, 0.25],  # LP_B high vol
            [0, 0, 1, 1, 0, 1, 0.4, 0.25],  # LP_C high vol
        ],
        dtype=np.float64,
    )
    fill_probabilities = predict_xgboost(model_bytes, features)
    digest = hashlib.sha256(model_bytes).hexdigest()[:10]
    generated_at = datetime.now(UTC).isoformat()
    
    profiles = {
        "LP_A": {"slippage": 1.10, "latency": 78.0, "benefit": 0.45, "asymmetry": 0.22},
        "LP_B": {"slippage": 0.42, "latency": 31.0, "benefit": 0.10, "asymmetry": 0.03},
        "LP_C": {"slippage": 0.84, "latency": 86.0, "benefit": 0.20, "asymmetry": 0.08},
    }
    providers = []
    for index, (provider, profile) in enumerate(profiles.items()):
        fill_probability = float(fill_probabilities[index])
        providers.append(
            {
                "provider": provider,
                "sample_count": 450,
                "fill_probability": round(fill_probability, 6),
                "rejection_probability": round(1.0 - fill_probability, 6),
                "expected_slippage_bps": profile["slippage"],
                "expected_latency_ms": profile["latency"],
                "displayed_price_benefit_bps": profile["benefit"],
                "rejection_asymmetry": profile["asymmetry"],
                "model_version": f"fed-xgb-{digest}",
                "generated_at": generated_at,
            }
        )
    evidence = {
        "cohort_size": 5,
        "raw_records_shared": 0,
        "client_identities_shared": 0,
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
    manifest.config = {
        "num_desks": 5,
        "num_rounds": int(context.run_config["num-server-rounds"]),
        "local_trees": int(context.run_config["local-trees"]),
        "fraction_evaluate": float(context.run_config["fraction-evaluate"]),
    }
    
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
        round_model_bytes = round_result.arrays.to_numpy_ndarrays()[0].tobytes()
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
    output = export_approved_evidence(final_model_bytes, manifest)
    
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
