"""Canada Productivity Intelligence ML package.

Modular pipelines for:
    * ETL from official Government of Canada data sources.
    * Feature engineering with strict temporal ordering (no look-ahead).
    * Forecasting (scikit-learn / XGBoost).
    * Explainability (SHAP-based feature attribution).

No module fabricates data, endpoints, or metrics.
"""

__version__ = "0.1.0"
