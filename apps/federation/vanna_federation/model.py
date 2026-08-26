"""Small NumPy logistic model suitable for transparent FedAvg."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .data import FEATURE_NAMES

Parameters = list[NDArray[np.float64]]


def initial_parameters() -> Parameters:
    return [
        np.zeros(len(FEATURE_NAMES), dtype=np.float64),
        np.zeros(1, dtype=np.float64),
    ]


def predict_probability(x: NDArray[np.float64], parameters: Parameters) -> NDArray[np.float64]:
    weights, bias = parameters
    logits = x @ weights + bias[0]
    return 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))


def train(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    parameters: Parameters,
    *,
    epochs: int,
    learning_rate: float,
) -> tuple[Parameters, float]:
    weights, bias = [array.copy() for array in parameters]
    for _ in range(epochs):
        probabilities = predict_probability(x, [weights, bias])
        error = probabilities - y
        weights -= learning_rate * (x.T @ error) / len(x)
        bias -= learning_rate * np.array([error.mean()])
    return [weights, bias], binary_cross_entropy(x, y, [weights, bias])


def binary_cross_entropy(
    x: NDArray[np.float64], y: NDArray[np.float64], parameters: Parameters
) -> float:
    probabilities = np.clip(predict_probability(x, parameters), 1e-8, 1 - 1e-8)
    return float(-np.mean(y * np.log(probabilities) + (1 - y) * np.log(1 - probabilities)))


def accuracy(
    x: NDArray[np.float64], y: NDArray[np.float64], parameters: Parameters
) -> float:
    predictions = predict_probability(x, parameters) >= 0.5
    return float(np.mean(predictions == y))
