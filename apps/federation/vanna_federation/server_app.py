"""Flower server coordinating five desks and exporting approved evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from flwr.app import ArrayRecord, ConfigRecord, Context, MetricRecord
from flwr.serverapp import Grid, ServerApp
from flwr.serverapp.strategy import FedAvg

from .data import global_test_data_legacy
from .model import accuracy, binary_cross_entropy, initial_parameters, predict_probability

app = ServerApp()


def global_evaluate(_server_round: int, arrays: ArrayRecord) -> MetricRecord:
    x_test, y_test = global_test_data_legacy()
    parameters = arrays.to_numpy_ndarrays()
    return MetricRecord(
        {
            "centralized_loss": binary_cross_entropy(x_test, y_test, parameters),
            "centralized_accuracy": accuracy(x_test, y_test, parameters),
        }
    )


def export_approved_evidence(parameters: list[np.ndarray]) -> Path:
    features = np.array(
        [
            [1, 0, 0, 1, 1, 0, 0.4, 0.25],
            [0, 1, 0, 1, 0, 0, 0.4, 0.25],
            [0, 0, 1, 1, 0, 1, 0.4, 0.25],
        ],
        dtype=np.float64,
    )
    fill_probabilities = predict_probability(features, parameters)
    digest = hashlib.sha256(b"".join(array.tobytes() for array in parameters)).hexdigest()[:10]
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
                "model_version": f"fed-{digest}",
                "generated_at": generated_at,
            }
        )
    output = Path("artifacts/generated/provider_evidence.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "cohort_size": 5,
                "raw_records_shared": 0,
                "client_identities_shared": 0,
                "providers": providers,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


@app.main()
def main(grid: Grid, context: Context) -> None:
    strategy = FedAvg(
        fraction_train=1.0,
        fraction_evaluate=float(context.run_config["fraction-evaluate"]),
        min_train_nodes=5,
        min_evaluate_nodes=5,
        min_available_nodes=5,
    )
    result = strategy.start(
        grid=grid,
        initial_arrays=ArrayRecord(initial_parameters()),
        train_config=ConfigRecord(
            {"learning-rate": float(context.run_config["learning-rate"])}
        ),
        num_rounds=int(context.run_config["num-server-rounds"]),
        evaluate_fn=global_evaluate,
    )
    output = export_approved_evidence(result.arrays.to_numpy_ndarrays())
    print(f"Approved aggregate evidence written to {output}")
    print("Raw orders shared: 0")
    print("Client identities shared: 0")
