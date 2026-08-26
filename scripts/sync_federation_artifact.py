"""Copy Flower's approved aggregate output into the AgentApp bundle."""

import json
from pathlib import Path
import shutil

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FEDERATION_ARTIFACTS = ROOT / "apps/federation/artifacts"
AGENT_ARTIFACTS = ROOT / "apps/agent/vanna_agent/artifacts"

# Approved evidence plus the artifacts behind the genuine local-vs-federated
# comparison: the final ensemble (all 5 desks) and one desk partition (what a
# single desk would know alone). The partition is converted to JSON because
# FABs cannot include .npz files (built-in flwr constraint).
COPIES = [
    (
        FEDERATION_ARTIFACTS / "generated/provider_evidence.json",
        AGENT_ARTIFACTS / "provider_evidence.json",
    ),
    (
        FEDERATION_ARTIFACTS / "final_ensemble/final_model.json",
        AGENT_ARTIFACTS / "federated_final_model.json",
    ),
]

DESK_PARTITION = FEDERATION_ARTIFACTS / "desk_partitions/desk_0.npz"
DESK_PARTITION_JSON = AGENT_ARTIFACTS / "local_desk_0.json"


def main() -> None:
    missing = [str(src) for src, _ in COPIES if not src.exists()]
    if not DESK_PARTITION.exists():
        missing.append(str(DESK_PARTITION))
    if missing:
        raise SystemExit(
            "Federation artifact(s) missing:\n  "
            + "\n  ".join(missing)
            + "\nRun `uv run flwr run . --federation-config=\"num-supernodes=5\" --stream` "
            "from apps/federation first."
        )
    AGENT_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for src, dst in COPIES:
        shutil.copy2(src, dst)
        print(f"Copied {src.name} -> {dst}")

    partition = np.load(DESK_PARTITION, allow_pickle=True)
    DESK_PARTITION_JSON.write_text(
        json.dumps(
            {
                "x_train": partition["x_train"].tolist(),
                "y_train": partition["y_train"].tolist(),
                "x_test": partition["x_test"].tolist(),
                "y_test": partition["y_test"].tolist(),
            }
        )
    )
    print(f"Converted {DESK_PARTITION.name} -> {DESK_PARTITION_JSON}")


if __name__ == "__main__":
    main()

