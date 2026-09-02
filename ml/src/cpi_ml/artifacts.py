"""Reproducible model artifact persistence.

An artifact is a directory under the configured artifacts dir containing:

    model.joblib   — the fitted estimator (scikit-learn pipeline or baseline).
    metadata.json  — full reproducibility metadata (see ModelMetadata).

We never save a bare model with no metadata. The metadata records exactly what
was predicted, which features were used and in what order, the preprocessing
configuration, the chronological train/validation/test boundaries, when it was
trained, the real evaluation metrics, and the forecast horizon — everything
needed to reproduce and to serve predictions safely.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

METADATA_FILENAME = "metadata.json"
MODEL_FILENAME = "model.joblib"


@dataclass
class ModelMetadata:
    """Everything needed to reproduce and safely serve a trained model."""

    model_type: str  # short key, e.g. "random_forest"
    algorithm: str  # human-readable label, e.g. "RandomForestRegressor(...)"
    model_version: str  # e.g. "labour_productivity-q1h-20260901T2200Z"
    target: str  # target measure, e.g. "Labour productivity"
    resolution: str  # "QUARTERLY"
    forecast_horizon: int  # periods ahead (1 = one quarter)
    feature_names: list[str]  # ordered — MUST match prediction input ordering
    preprocessing: dict[str, Any]  # imputation/scaling config summary
    training_period: dict[str, str | None]  # {"start":..., "end":...}
    validation_period: dict[str, str | None]
    test_period: dict[str, str | None]
    trained_at: str  # ISO-8601 UTC
    metrics: dict[str, Any]  # per-model + selected metrics (real backtests)
    feature_set_id: str | None = None  # provenance: which FeatureSet was used
    n_train_rows: int = 0
    n_val_rows: int = 0
    n_test_rows: int = 0
    random_seed: int = 42
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def utc_now_iso() -> str:
    """Current UTC timestamp as an ISO-8601 string (second precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_model_version(target: str, horizon: int, trained_at: str | None = None) -> str:
    """Deterministic-ish version string embedding target, horizon, timestamp."""
    ts = (trained_at or utc_now_iso()).replace("-", "").replace(":", "")
    slug = target.lower().replace(" ", "_")
    return f"{slug}-h{horizon}-{ts}"


def save_artifact(model: Any, metadata: ModelMetadata, artifacts_dir: str | Path) -> Path:
    """Persist ``model`` + ``metadata`` into ``artifacts_dir/<model_version>/``.

    Returns the artifact directory path. Also refreshes a ``latest`` pointer
    file so serving code can find the most recent model without scanning.
    """
    base = Path(artifacts_dir)
    artifact_dir = base / metadata.model_version
    artifact_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, artifact_dir / MODEL_FILENAME)
    (artifact_dir / METADATA_FILENAME).write_text(metadata.to_json(), encoding="utf-8")

    # Record the latest version so `predict` can default to it.
    (base / "latest.txt").write_text(metadata.model_version, encoding="utf-8")
    return artifact_dir


def _resolve_artifact_dir(artifacts_dir: str | Path, model_version: str | None) -> Path:
    base = Path(artifacts_dir)
    if model_version:
        return base / model_version
    latest_ptr = base / "latest.txt"
    if not latest_ptr.exists():
        raise FileNotFoundError(
            f"no model_version given and no latest pointer at {latest_ptr}; train a model first"
        )
    return base / latest_ptr.read_text(encoding="utf-8").strip()


def load_metadata(artifacts_dir: str | Path, model_version: str | None = None) -> ModelMetadata:
    """Load just the metadata for an artifact (no model deserialization)."""
    artifact_dir = _resolve_artifact_dir(artifacts_dir, model_version)
    payload = json.loads((artifact_dir / METADATA_FILENAME).read_text(encoding="utf-8"))
    return ModelMetadata(**payload)


def load_artifact(
    artifacts_dir: str | Path, model_version: str | None = None
) -> tuple[Any, ModelMetadata]:
    """Load ``(model, metadata)`` for a version (or the latest if None)."""
    artifact_dir = _resolve_artifact_dir(artifacts_dir, model_version)
    model = joblib.load(artifact_dir / MODEL_FILENAME)
    metadata = load_metadata(artifacts_dir, model_version)
    return model, metadata
