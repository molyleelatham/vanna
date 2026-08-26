"""Participant-side Flower app; each invocation sees one desk partition.

Uses FedXgbBagging strategy: each client trains local XGBoost trees
and returns updated model bytes.
Includes desk partition persistence.
"""

import numpy as np
from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp

from .data import generate_desk_data_legacy, DeskData
from .xgboost_federated import (
    train_xgboost_local,
    evaluate_xgboost,
    bytes_to_xgb_model,
)
from .persistence import save_desk_partition, load_desk_partition

app = ClientApp()


@app.train()
def train(msg: Message, context: Context) -> Message:
    partition_id = int(context.node_config["partition-id"])
    
    # Try to load existing partition data
    loaded = load_desk_partition(partition_id)
    if loaded:
        _, x_train, y_train, _, _ = loaded
        # Create DeskData with loaded data (reuse test data from legacy)
        legacy_data = generate_desk_data_legacy(partition_id)
        data = DeskData(
            x_train=x_train, y_train=y_train,
            x_test=legacy_data.x_test, y_test=legacy_data.y_test
        )
    else:
        # Generate and persist
        legacy_data = generate_desk_data_legacy(partition_id)
        data = legacy_data
        from .desk_config import DEFAULT_DESK_CONFIGS
        save_desk_partition(
            partition_id,
            DEFAULT_DESK_CONFIGS[partition_id].to_dict(),
            data.x_train, data.y_train,
            data.x_test, data.y_test
        )
    
    # Receive global XGBoost model as bytes
    global_model_bytes = msg.content["arrays"].to_numpy_ndarrays()[0].tobytes()
    
    # Train locally
    updated_bytes, loss = train_xgboost_local(
        data.x_train,
        data.y_train,
        global_model_bytes,
        num_local_trees=int(context.run_config["local-trees"]),
    )
    
    # Return updated model as bytes array
    content = RecordDict(
        {
            "arrays": ArrayRecord([np.frombuffer(updated_bytes, dtype=np.uint8)]),
            "metrics": MetricRecord(
                {
                    "train_loss": loss,
                    "num-examples": len(data.y_train),
                    "raw-records-shared": 0,
                }
            ),
        }
    )
    return Message(content=content, reply_to=msg)


@app.evaluate()
def evaluate(msg: Message, context: Context) -> Message:
    partition_id = int(context.node_config["partition-id"])
    
    # Try to load existing partition data
    loaded = load_desk_partition(partition_id)
    if loaded:
        _, _, _, x_test, y_test = loaded
    else:
        legacy_data = generate_desk_data_legacy(partition_id)
        x_test, y_test = legacy_data.x_test, legacy_data.y_test
    
    global_model_bytes = msg.content["arrays"].to_numpy_ndarrays()[0].tobytes()
    metrics_dict = evaluate_xgboost(global_model_bytes, x_test, y_test)
    
    metrics = MetricRecord(
        {
            "eval_loss": metrics_dict["logloss"],
            "eval_accuracy": metrics_dict["accuracy"],
            "num-examples": len(y_test),
        }
    )
    return Message(content=RecordDict({"metrics": metrics}), reply_to=msg)
