"""SecAgg+ secure aggregation mode for the five-desk federation.

Runs FedAvg over the transparent NumPy logistic model under Flower's
SecAgg+ protocol: the server only ever recovers the masked weighted
average of desk updates. Individual updates are never exposed, so
per-round checkpoints contain the aggregate only.

SecAgg+ is a summation protocol and cannot merge XGBoost trees, so this
mode is opt-in via the ``secure-aggregation`` run config and leaves the
default FedXgbBagging path untouched.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from flwr.common import (
    Metrics,
    NDArray,
    NDArrays,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.compat.common.recorddict_compat import arrayrecord_to_parameters
from flwr.server import LegacyContext, ServerConfig
from flwr.server.strategy import FedAvg
from flwr.server.workflow import DefaultWorkflow, SecAggPlusWorkflow
from flwr.server.workflow.constant import MAIN_PARAMS_RECORD
from flwr.serverapp import Grid
from flwr.app import Context

from .data import global_test_data_legacy
from .model import accuracy, binary_cross_entropy, initial_parameters
from .persistence import TrainingManifest, save_model_checkpoint


def _weighted_average(metrics: list[tuple[int, Metrics]]) -> Metrics:
    """Aggregate distributed evaluation metrics weighted by examples."""
    accuracies = [num * float(m["eval_accuracy"]) for num, m in metrics]
    losses = [num * float(m["eval_loss"]) for num, m in metrics]
    examples = [num for num, _ in metrics]
    total = sum(examples)
    return {
        "eval_accuracy": sum(accuracies) / total,
        "eval_loss": sum(losses) / total,
    }


def _weighted_average_fit(metrics: list[tuple[int, Metrics]]) -> Metrics:
    """Aggregate distributed fit metrics (train_loss) weighted by examples."""
    losses = [num * float(m["train_loss"]) for num, m in metrics]
    total = sum(num for num, _ in metrics)
    return {"train_loss": sum(losses) / total}


def _central_evaluate(
    server_round: int, parameters: NDArrays, _config: dict[str, Scalar]
) -> tuple[float, dict[str, Scalar]]:
    """Centralized evaluation of the logistic model on the global test set."""
    x_test, y_test = global_test_data_legacy()
    params = [np.asarray(array, dtype=np.float64) for array in parameters]
    loss = binary_cross_entropy(x_test, y_test, params)
    acc = accuracy(x_test, y_test, params)
    return loss, {"centralized_loss": loss, "centralized_accuracy": acc}


class CheckpointingFedAvg(FedAvg):
    """FedAvg that checkpoints the securely aggregated parameters per round.

    Under SecAgg+ the strategy only ever receives the reconstructed
    weighted average (individual masked updates are never visible), so
    checkpoints preserve the privacy guarantee by construction.
    """

    def __init__(self, manifest: TrainingManifest, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.manifest = manifest

    def aggregate_fit(self, server_round, results, failures):
        aggregated_parameters, aggregated_metrics = super().aggregate_fit(
            server_round, results, failures
        )
        if aggregated_parameters is not None:
            arrays = parameters_to_ndarrays(aggregated_parameters)
            model_bytes = b"".join(
                np.asarray(array, dtype=np.float64).tobytes() for array in arrays
            )
            metrics = {
                "train_loss": float(
                    (aggregated_metrics or {}).get("train_loss", 0.0)
                ),
                "secure_aggregation": "secaggplus",
            }
            save_model_checkpoint(model_bytes, server_round, self.manifest, metrics)
        return aggregated_parameters, aggregated_metrics


def run_secure_federation(
    grid: Grid, context: Context, manifest: TrainingManifest
) -> list[NDArray]:
    """Run all FedAvg rounds under SecAgg+ and return the final parameters."""
    num_rounds = int(context.run_config["num-server-rounds"])
    local_epochs = int(context.run_config["local-epochs"])
    learning_rate = float(context.run_config["learning-rate"])

    strategy = CheckpointingFedAvg(
        manifest=manifest,
        fraction_fit=1.0,
        fraction_evaluate=float(context.run_config["fraction-evaluate"]),
        min_fit_clients=5,
        min_evaluate_clients=5,
        min_available_clients=5,
        evaluate_fn=_central_evaluate,
        on_fit_config_fn=lambda _round: {
            "local-epochs": local_epochs,
            "learning-rate": learning_rate,
        },
        fit_metrics_aggregation_fn=_weighted_average_fit,
        evaluate_metrics_aggregation_fn=_weighted_average,
        initial_parameters=ndarrays_to_parameters(initial_parameters()),
    )

    fit_workflow = SecAggPlusWorkflow(
        num_shares=int(context.run_config["num-shares"]),
        reconstruction_threshold=int(context.run_config["reconstruction-threshold"]),
        max_weight=float(context.run_config["max-weight"]),
        timeout=float(context.run_config["secagg-timeout"]),
    )
    workflow = DefaultWorkflow(fit_workflow=fit_workflow)

    legacy_context = LegacyContext(
        context=context,
        config=ServerConfig(num_rounds=num_rounds),
        strategy=strategy,
    )
    workflow(grid, legacy_context)

    final_record = legacy_context.state.array_records[MAIN_PARAMS_RECORD]
    parameters = parameters_to_ndarrays(
        arrayrecord_to_parameters(final_record, keep_input=True)
    )
    return [np.asarray(array, dtype=np.float64) for array in parameters]
