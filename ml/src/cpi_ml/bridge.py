"""JSON stdin/stdout bridge between the Express backend and the ML model.

The backend already retrieves feature data from the database itself (via
Prisma). This bridge exists only to run the trained model — predict, explain,
report model info, and expose feature metadata — so Python internals are never
touched directly by the frontend.

Protocol (single request/response per process invocation):

    stdin  : {"action": "...", ...}
    stdout : {"ok": true, "result": {...}}  on success
             {"ok": false, "error": "...", "code": "..."}  on failure

Actions:
    predict          {features: {...}, model_version?, forecast_period?}
    explain          {features: {...}, model_version?, forecast_period?}
    forecast         predict + explain in one call (used by /api/v1/forecast)
    model_info       {model_version?}  -> metadata for /api/v1/models
    feature_metadata {}                -> central feature metadata + scenario flags

The bridge never fabricates values. If the model artifact is missing, it returns
a structured error the backend maps to an HTTP status.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Artifacts live at ml/artifacts (this file is ml/src/cpi_ml/bridge.py).
_ARTIFACTS_DIR = str(Path(__file__).resolve().parents[2] / "artifacts")


def _error(message: str, code: str = "error") -> dict:
    return {"ok": False, "error": message, "code": code}


def _load_forecaster(model_version: str | None):
    from cpi_ml.prediction import ProductivityForecaster

    return ProductivityForecaster.load(_ARTIFACTS_DIR, model_version)


def _model_info(model_version: str | None) -> dict:
    """Serializable model metadata for the /api/v1/models endpoint.

    Filesystem paths and secrets are intentionally excluded.
    """
    from cpi_ml.artifacts import load_metadata

    meta = load_metadata(_ARTIFACTS_DIR, model_version)
    latest_ptr = Path(_ARTIFACTS_DIR) / "latest.txt"
    active_version = latest_ptr.read_text(encoding="utf-8").strip() if latest_ptr.exists() else None
    return {
        "model_version": meta.model_version,
        "model_type": meta.model_type,
        "algorithm": meta.algorithm,
        "target": meta.target,
        "resolution": meta.resolution,
        "forecast_horizon": meta.forecast_horizon,
        "feature_names": meta.feature_names,
        "training_period": meta.training_period,
        "validation_period": meta.validation_period,
        "test_period": meta.test_period,
        "trained_at": meta.trained_at,
        "metrics": meta.metrics,
        "is_active": meta.model_version == active_version,
    }


def _feature_metadata() -> dict:
    """Central feature metadata + scenario eligibility for validation/UI."""
    from cpi_ml.feature_metadata import FEATURE_METADATA, scenario_eligible_features

    return {
        "features": {name: meta.as_dict() for name, meta in FEATURE_METADATA.items()},
        "scenario_eligible": scenario_eligible_features(),
    }


def handle(request: dict[str, Any]) -> dict:
    action = request.get("action")
    model_version = request.get("model_version")
    forecast_period = request.get("forecast_period")
    features = request.get("features") or {}

    if action == "model_info":
        return {"ok": True, "result": _model_info(model_version)}

    if action == "feature_metadata":
        return {"ok": True, "result": _feature_metadata()}

    if action == "predict_batch":
        # Predict many labeled feature vectors in ONE process (model loaded
        # once). Used by the overview comparison so N industries cost a single
        # process spawn instead of N. Each item: {id, features, forecast_period?}.
        items = request.get("items")
        if not isinstance(items, list) or not items:
            return _error("items list is required", code="missing_features")
        forecaster = _load_forecaster(model_version)
        predictions: list[dict[str, Any]] = []
        for item in items:
            feats = item.get("features") or {}
            if not isinstance(feats, dict) or not feats:
                continue  # skip items without features rather than fabricate
            pred = forecaster.predict(feats, forecast_period=item.get("forecast_period"))
            predictions.append({"id": item.get("id"), "prediction": pred.as_dict()})
        return {"ok": True, "result": {"predictions": predictions}}

    if action in {"predict", "explain", "forecast"}:
        if not isinstance(features, dict) or not features:
            return _error("features mapping is required", code="missing_features")
        forecaster = _load_forecaster(model_version)
        result: dict[str, Any] = {}
        if action in {"predict", "forecast"}:
            pred = forecaster.predict(features, forecast_period=forecast_period)
            result["prediction"] = pred.as_dict()
        if action in {"explain", "forecast"}:
            expl = forecaster.explain(features, forecast_period=forecast_period)
            result["explanation"] = expl.as_dict()
        return {"ok": True, "result": result}

    return _error(f"unknown action: {action!r}", code="unknown_action")


def main() -> int:
    try:
        raw = sys.stdin.read()
        request = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(json.dumps(_error(f"invalid JSON request: {exc}", code="bad_request")))
        return 0

    try:
        response = handle(request)
    except FileNotFoundError as exc:
        response = _error(str(exc), code="model_missing")
    except Exception as exc:  # noqa: BLE001 - bridge must always emit JSON
        response = _error(f"{type(exc).__name__}: {exc}", code="internal_error")

    print(json.dumps(response))
    return 0


if __name__ == "__main__":
    sys.exit(main())
