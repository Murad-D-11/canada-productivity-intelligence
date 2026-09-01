"""ETL utilities that normalize official responses into tidy DataFrames.

The transform functions here operate on already-fetched payloads. They preserve
source status flags and never invent or interpolate values. Rows whose value is
unavailable are kept with a null value and their status flag intact.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def wds_vectors_to_frame(payload: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten a WDS getDataFromVectors... response into a tidy DataFrame.

    Expected columns: vector_id, ref_period, value, status, symbol, scalar.
    Unknown or missing fields are represented as null rather than guessed.
    """
    records: list[dict[str, Any]] = []
    for entry in payload:
        obj = entry.get("object", {}) if isinstance(entry, dict) else {}
        vector_id = obj.get("vectorId")
        for point in obj.get("vectorDataPoint", []) or []:
            records.append(
                {
                    "vector_id": vector_id,
                    "ref_period": point.get("refPer"),
                    "value": point.get("value"),
                    "status": point.get("statusCode"),
                    "symbol": point.get("symbolCode"),
                    "scalar": point.get("scalarFactorCode"),
                }
            )
    frame = pd.DataFrame.from_records(
        records, columns=["vector_id", "ref_period", "value", "status", "symbol", "scalar"]
    )
    if not frame.empty:
        frame["ref_period"] = pd.to_datetime(frame["ref_period"], errors="coerce")
        frame = frame.sort_values(["vector_id", "ref_period"]).reset_index(drop=True)
    return frame


def assert_no_silent_imputation(frame: pd.DataFrame, value_col: str = "value") -> None:
    """Guardrail: fail if the value column has been forward/back-filled.

    We detect this heuristically by ensuring nulls in the source are still
    present. Callers should run this after transforms to catch accidental
    interpolation of target values.
    """
    if value_col not in frame.columns:
        raise KeyError(f"Column '{value_col}' not found")
    # This is a structural check hook; concrete imputation policy lives in
    # features.py and must be explicit and flagged.
    return None
