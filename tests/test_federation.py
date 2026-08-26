import json

import numpy as np
import pytest

from vanna_federation.data import generate_desk_data, global_test_data
from vanna_federation.model import (
    accuracy,
    binary_cross_entropy,
    initial_parameters,
    train,
)
from vanna_federation.privacy import validate_shared_payload
from vanna_federation.server_app import export_approved_evidence


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


def test_desk_vault_stays_local_and_export_has_no_identifiers(tmp_path, monkeypatch) -> None:
    data = generate_desk_data(0)
    assert data.vault.desk_id == 0
    assert data.vault.entries
    first = data.vault.entries[0]
    assert data.vault.reveal(first.hash_id) == first
    assert first.local_order_id.startswith("DESK0-ORD-")
    assert first.uti.startswith("UTI-0-")
    assert first.hash_id != first.local_order_id

    shared = {
        "train_loss": 0.5,
        "num-examples": len(data.y_train),
        "raw-records-shared": 0,
        "payload-bytes": 64,
    }
    validate_shared_payload(shared)
    with pytest.raises(ValueError, match="prohibited"):
        validate_shared_payload({"train_loss": 0.5, "local_order_id": first.local_order_id})

    monkeypatch.chdir(tmp_path)
    path = export_approved_evidence(initial_parameters())
    payload = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(payload)
    assert first.local_order_id not in blob
    assert first.uti not in blob
    assert first.client_id not in blob
    assert first.hash_id not in blob
    assert data.vault.secret not in blob
    assert payload["raw_records_shared"] == 0
    assert payload["client_identities_shared"] == 0
