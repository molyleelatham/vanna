"""Tests for the opt-in SecAgg+ secure aggregation mode."""

import numpy as np
import pytest
from flwr.app import ArrayRecord, ConfigRecord, Context, Message, RecordDict
from flwr.app.message_type import MessageType
from flwr.common import ndarrays_to_parameters, parameters_to_ndarrays
from flwr.common.secure_aggregation.secaggplus_constants import (
    RECORD_KEY_CONFIGS,
    Key,
    Stage,
)
from flwr.compat.common.recorddict_compat import (
    parameters_to_arrayrecord,
    recorddict_to_fitres,
)

from vanna_federation.client_app import _train_secure, secure_aggregation_mod
from vanna_federation.data import generate_desk_data_legacy
from vanna_federation.model import initial_parameters
from vanna_federation.privacy import validate_shared_payload
from vanna_federation.secagg import _central_evaluate, _weighted_average


def _context(run_config: dict) -> Context:
    return Context(
        run_id=1,
        node_id=0,
        node_config={},
        state=RecordDict(),
        run_config=run_config,
    )


def _secure_train_message() -> Message:
    params_record = parameters_to_arrayrecord(
        ndarrays_to_parameters(initial_parameters()), keep_input=True
    )
    content = RecordDict({"fitins.parameters": params_record})
    return Message(
        content=content,
        dst_node_id=7,
        message_type=MessageType.TRAIN,
        group_id="1",
    )


def test_secure_train_reply_matches_secaggplus_fitres_contract() -> None:
    data = generate_desk_data_legacy(0)
    context = _context({"local-epochs": 2, "learning-rate": 0.15})

    reply = _train_secure(_secure_train_message(), context, data)

    fit_res = recorddict_to_fitres(reply.content, keep_input=True)
    arrays = parameters_to_ndarrays(fit_res.parameters)
    assert [array.shape for array in arrays] == [(8,), (1,)]
    assert fit_res.num_examples == 360
    assert fit_res.metrics["raw-records-shared"] == 0
    validate_shared_payload(fit_res.metrics)


def test_mod_passes_plain_xgboost_train_message_through() -> None:
    content = RecordDict({"arrays": ArrayRecord([np.zeros(4, dtype=np.uint8)])})
    msg = Message(content=content, dst_node_id=7, message_type=MessageType.TRAIN)
    sentinel = Message(content=RecordDict(), reply_to=msg)

    def call_next(m, c):
        return sentinel

    assert secure_aggregation_mod(msg, _context({}), call_next) is sentinel


def test_mod_routes_secagg_setup_stage_to_secaggplus() -> None:
    configs = ConfigRecord(
        {
            Key.STAGE: Stage.SETUP,
            Key.SAMPLE_NUMBER: 5,
            Key.SHARE_NUMBER: 5,
            Key.THRESHOLD: 3,
            Key.CLIPPING_RANGE: 8.0,
            Key.TARGET_RANGE: 4194304,
            Key.MOD_RANGE: 4294967296,
            Key.MAX_WEIGHT: 1000.0,
        }
    )
    content = RecordDict({RECORD_KEY_CONFIGS: configs})
    msg = Message(
        content=content,
        dst_node_id=7,
        message_type=MessageType.TRAIN,
        group_id="1",
    )

    def call_next(m, c):
        raise AssertionError("inner app must not run during the setup stage")

    reply = secure_aggregation_mod(msg, _context({}), call_next)

    assert RECORD_KEY_CONFIGS in reply.content.config_records
    out_configs = reply.content.config_records[RECORD_KEY_CONFIGS]
    assert Key.PUBLIC_KEY_1 in out_configs
    assert Key.PUBLIC_KEY_2 in out_configs


def test_validate_shared_payload_rejects_raw_identifiers() -> None:
    with pytest.raises(ValueError):
        validate_shared_payload({"client_id": "desk-3", "train_loss": 0.1})


def test_central_evaluate_returns_finite_metrics() -> None:
    loss, metrics = _central_evaluate(1, initial_parameters(), {})
    assert 0.0 < loss < 1.0
    assert 0.0 <= metrics["centralized_accuracy"] <= 1.0


def test_weighted_average() -> None:
    metrics = [
        (360, {"eval_accuracy": 0.5, "eval_loss": 1.0}),
        (360, {"eval_accuracy": 1.0, "eval_loss": 0.0}),
    ]
    aggregated = _weighted_average(metrics)
    assert aggregated["eval_accuracy"] == pytest.approx(0.75)
    assert aggregated["eval_loss"] == pytest.approx(0.5)
