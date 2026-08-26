"""Participant-side Flower app; each invocation sees one desk partition."""

from flwr.app import ArrayRecord, Context, Message, MetricRecord, RecordDict
from flwr.clientapp import ClientApp

from .data import generate_desk_data_legacy
from .model import accuracy, binary_cross_entropy, train as train_model

app = ClientApp()


@app.train()
def train(msg: Message, context: Context) -> Message:
    partition_id = int(context.node_config["partition-id"])
    data = generate_desk_data_legacy(partition_id)
    parameters = msg.content["arrays"].to_numpy_ndarrays()
    updated, loss = train_model(
        data.x_train,
        data.y_train,
        parameters,
        epochs=int(context.run_config["local-epochs"]),
        learning_rate=float(msg.content["config"]["learning-rate"]),
    )
    content = RecordDict(
        {
            "arrays": ArrayRecord(updated),
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
    data = generate_desk_data_legacy(partition_id)
    parameters = msg.content["arrays"].to_numpy_ndarrays()
    metrics = MetricRecord(
        {
            "eval_loss": binary_cross_entropy(data.x_test, data.y_test, parameters),
            "eval_accuracy": accuracy(data.x_test, data.y_test, parameters),
            "num-examples": len(data.y_test),
        }
    )
    return Message(content=RecordDict({"metrics": metrics}), reply_to=msg)
