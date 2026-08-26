import numpy as np

from vanna_federation.data import generate_desk_data, global_test_data
from vanna_federation.model import (
    accuracy,
    binary_cross_entropy,
    initial_parameters,
    train,
)


def test_five_partitions_are_distinct_and_reproducible() -> None:
    partitions = [generate_desk_data(index) for index in range(5)]
    assert all(len(partition.y_train) == 360 for partition in partitions)
    assert np.array_equal(partitions[0].x_train, generate_desk_data(0).x_train)
    assert not np.array_equal(partitions[0].x_train, partitions[1].x_train)


def test_one_fedavg_round_improves_global_model() -> None:
    initial = initial_parameters()
    updates = []
    for index in range(5):
        data = generate_desk_data(index)
        updated, _ = train(
            data.x_train,
            data.y_train,
            initial,
            epochs=8,
            learning_rate=0.15,
        )
        updates.append(updated)
    aggregated = [
        np.mean([update[array_index] for update in updates], axis=0)
        for array_index in range(len(initial))
    ]
    x_test, y_test = global_test_data()
    assert binary_cross_entropy(x_test, y_test, aggregated) < binary_cross_entropy(
        x_test, y_test, initial
    )
    assert accuracy(x_test, y_test, aggregated) >= accuracy(x_test, y_test, initial)
