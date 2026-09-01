# ML — Canada Productivity Intelligence

Python package (`cpi_ml`) providing ETL, feature engineering, forecasting, and
SHAP-based explainability for Canadian productivity data.

## Stack

- Python 3.11+
- pandas / NumPy
- scikit-learn / XGBoost
- SHAP for explainability
- requests (official data-source clients)
- pydantic-settings (config), SQLAlchemy (DB access)

## Package layout

```
ml/
  src/cpi_ml/
    config.py         env-driven settings
    datasources/      StatCan WDS + MSC GeoMet clients (live endpoints only)
    etl.py            normalize responses into tidy frames (no silent imputation)
    features.py       lag/rolling features with strict temporal ordering
    forecasting.py    expanding-window backtest + metrics
    explainability.py SHAP aggregation (association, not causation)
    cli.py            `cpi-ml` command-line entry point
  tests/              unit tests for features, backtesting, attribution
```

## Setup

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
cpi-ml --version
cpi-ml config     # print resolved configuration
cpi-ml sources    # show configured official data sources
python -m cpi_ml.cli --help
```

## Testing & quality

```bash
pytest          # run unit tests
ruff check .    # lint
mypy src        # type-check
```

## Data integrity commitments

- Data-source clients call only the real, documented Government of Canada
  endpoints; no responses are fabricated.
- Target values are never silently interpolated. Missing observations remain
  null with their source status flag preserved.
- Features use only past information relative to each period (no look-ahead).
- Backtest metrics are computed from genuine out-of-sample folds, never
  hard-coded.
- SHAP attributions describe association, not causation.
