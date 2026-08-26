"""Persistence layer for federated XGBoost training state.

Implements checkpointing, manifest tracking, and data persistence
following Flower's SaveModelStrategy pattern and fraud detection app.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


# Directory structure
ARTIFACTS_DIR = Path("artifacts")
CHECKPOINTS_DIR = ARTIFACTS_DIR / "checkpoints"
FINAL_ENSEMBLE_DIR = ARTIFACTS_DIR / "final_ensemble"
DESK_DATA_DIR = ARTIFACTS_DIR / "desk_partitions"
GENERATED_DIR = ARTIFACTS_DIR / "generated"


def ensure_dirs() -> None:
    """Create all artifact directories."""
    for dir_path in [CHECKPOINTS_DIR, FINAL_ENSEMBLE_DIR, DESK_DATA_DIR, GENERATED_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


class TrainingManifest:
    """Training run manifest for audit and reproducibility."""
    
    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or f"fed-xgb-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        self.started_at = datetime.now(UTC).isoformat()
        self.completed_at: str | None = None
        self.config: dict[str, Any] = {}
        self.rounds: list[dict[str, Any]] = []
        self.final_model_path: str | None = None
        self.feature_importance_path: str | None = None
        self.provider_evidence_path: str | None = None
    
    def add_round(self, round_num: int, metrics: dict[str, Any], model_path: str) -> None:
        self.rounds.append({
            "round": round_num,
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": metrics,
            "model_path": model_path,
        })
    
    def complete(self, final_model_path: str, feature_importance_path: str, evidence_path: str) -> None:
        self.completed_at = datetime.now(UTC).isoformat()
        self.final_model_path = final_model_path
        self.feature_importance_path = feature_importance_path
        self.provider_evidence_path = evidence_path
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "config": self.config,
            "rounds": self.rounds,
            "final_model_path": self.final_model_path,
            "feature_importance_path": self.feature_importance_path,
            "provider_evidence_path": self.provider_evidence_path,
        }
    
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
    
    @classmethod
    def load(cls, path: Path) -> "TrainingManifest":
        data = json.loads(path.read_text())
        manifest = cls(data["run_id"])
        manifest.started_at = data["started_at"]
        manifest.completed_at = data.get("completed_at")
        manifest.config = data.get("config", {})
        manifest.rounds = data.get("rounds", [])
        manifest.final_model_path = data.get("final_model_path")
        manifest.feature_importance_path = data.get("feature_importance_path")
        manifest.provider_evidence_path = data.get("provider_evidence_path")
        return manifest


def save_model_checkpoint(model_bytes: bytes, round_num: int, manifest: TrainingManifest, 
                         metrics: dict[str, Any] | None = None) -> str:
    """Save model checkpoint for a training round."""
    ensure_dirs()
    model_path = CHECKPOINTS_DIR / f"round_{round_num}_model.json"
    model_path.write_bytes(model_bytes)
    manifest.add_round(round_num, metrics or {}, str(model_path))
    return str(model_path)


def save_final_ensemble(model_bytes: bytes, manifest: TrainingManifest) -> str:
    """Save final ensemble model for inference."""
    ensure_dirs()
    # Save as single model file
    final_path = FINAL_ENSEMBLE_DIR / "final_model.json"
    final_path.write_bytes(model_bytes)
    # Also save to generated for backward compat
    gen_path = GENERATED_DIR / "final_model.json"
    gen_path.write_bytes(model_bytes)
    return str(final_path)


def save_feature_importance(importance: dict[str, float], manifest: TrainingManifest) -> str:
    """Save feature importance for the final model."""
    ensure_dirs()
    path = GENERATED_DIR / "feature_importance.json"
    path.write_text(json.dumps(importance, indent=2))
    manifest.feature_importance_path = str(path)
    return str(path)


def save_provider_evidence(evidence: dict[str, Any], manifest: TrainingManifest) -> str:
    """Save provider evidence artifact."""
    ensure_dirs()
    path = GENERATED_DIR / "provider_evidence.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    manifest.provider_evidence_path = str(path)
    return str(path)


def save_training_manifest(manifest: TrainingManifest) -> str:
    """Save complete training manifest."""
    ensure_dirs()
    path = ARTIFACTS_DIR / "training_manifest.json"
    manifest.save(path)
    return str(path)


def compute_model_digest(model_bytes: bytes) -> str:
    """Compute short digest for model versioning."""
    return hashlib.sha256(model_bytes).hexdigest()[:10]


# Desk data persistence
def save_desk_partition(partition_id: int, config: dict[str, Any], 
                       x_train: np.ndarray, y_train: np.ndarray,
                       x_test: np.ndarray, y_test: np.ndarray) -> str:
    """Save desk partition data to disk."""
    ensure_dirs()
    path = DESK_DATA_DIR / f"desk_{partition_id}.npz"
    np.savez_compressed(
        path,
        x_train=x_train, y_train=y_train,
        x_test=x_test, y_test=y_test,
        config=json.dumps(config),
    )
    return str(path)


def load_desk_partition(partition_id: int) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """Load desk partition data from disk."""
    path = DESK_DATA_DIR / f"desk_{partition_id}.npz"
    if not path.exists():
        return None
    loaded = np.load(path, allow_pickle=True)
    config = json.loads(str(loaded["config"]))
    return (
        config,
        loaded["x_train"], loaded["y_train"],
        loaded["x_test"], loaded["y_test"],
    )


def load_or_generate_desk_data(
    partition_id: int,
    config: Any,  # DeskConfig
    generate_fn: callable,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load desk data from disk or generate if not present."""
    from .desk_config import DeskConfig
    config_dict = config.to_dict() if hasattr(config, "to_dict") else config
    
    saved = load_desk_partition(partition_id)
    if saved:
        saved_config, x_train, y_train, x_test, y_test = saved
        # Verify config matches
        if saved_config.get("partition_id") == partition_id:
            return x_train, y_train, x_test, y_test
    
    # Generate and save
    data = generate_fn(config)
    save_desk_partition(partition_id, config_dict, data.x_train, data.y_train, data.x_test, data.y_test)
    return data.x_train, data.y_train, data.x_test, data.y_test