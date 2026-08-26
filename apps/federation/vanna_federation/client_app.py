"""Participant-side Flower app; each invocation sees one desk partition."""

from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp

from .data import generate_desk_data
from .model import accuracy, binary_cross_entropy, train as train_model
from .privacy import validate_shared_payload

app = ClientApp()


def _shared_train_metrics(loss: float, num_examples: int, payload_bytes: int) -> MetricRecord:
    metrics = {
        "train_loss": loss,
        "num-examples": num_examples,
        "raw-records-shared": 0,
        "payload-bytes": payload_bytes,
    }
    validate_shared_payload(metrics)
    return MetricRecord(metrics)


@app.train()
def train(msg: Message, context: Context) -> Message:
    partition_id = int(context.node_config["partition-id"])
    data = generate_desk_data(partition_id)
    # Vault stays in this process. It is not attached to the reply.
    if data.vault.desk_id != partition_id:
        raise RuntimeError("desk vault does not match partition")
    parameters = msg.content["arrays"].to_numpy_ndarrays()
    updated, loss = train_model(
        data.x_train,
        data.y_train,
        parameters,
        epochs=int(context.run_config["local-epochs"]),
        learning_rate=float(msg.content["config"]["learning-rate"]),
    )
    payload_bytes = int(sum(array.nbytes for array in updated))
    content = RecordDict(
        {
            "arrays": ArrayRecord(updated),
            "metrics": _shared_train_metrics(loss, len(data.y_train), payload_bytes),
        }
    )
    return Message(content=content, reply_to=msg)


@app.evaluate()
def evaluate(msg: Message, context: Context) -> Message:
    partition_id = int(context.node_config["partition-id"])
    data = generate_desk_data(partition_id)
    parameters = msg.content["arrays"].to_numpy_ndarrays()
    metrics = {
        "eval_loss": binary_cross_entropy(data.x_test, data.y_test, parameters),
        "eval_accuracy": accuracy(data.x_test, data.y_test, parameters),
        "num-examples": len(data.y_test),
        "raw-records-shared": 0,
    }
    validate_shared_payload(metrics)
    return Message(content=RecordDict({"metrics": MetricRecord(metrics)}), reply_to=msg)
