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
    features_pipeline.py  builds + persists the ML-ready FeatureSet/FeatureRow
    forecasting.py    problem definition, chronological splits, backtest + metrics
    models.py         naive baseline, ridge, random-forest model factories
    training.py       train / evaluate / select / persist a forecasting model
    artifacts.py      reproducible model artifact (model + full metadata)
    prediction.py     CLI-independent predict(features) interface
    explainability.py SHAP aggregation (association, not causation)
    cli.py            `cpi-ml` command-line entry point
  tests/              unit tests for features, backtesting, training, prediction
```

## Forecasting: what is predicted and how

### Prediction problem

- **Target** — the next-period **Labour productivity** value for a
  `(industry, geography)` series, i.e. `y[t + horizon]`. This is the productivity
  measure ingested by the StatCan pipeline (cube 36-10-0207-01).
- **Data** — the persisted feature matrix (`FeatureSet` / `FeatureRow`) built
  from ingested productivity observations. Coverage in the current dataset:
  21 industries, geography = Canada (national only), quarterly periods from
  1981 to 2026. Weather features exist in the schema but are excluded when
  weather has not been ingested (they would be entirely null).
- **Temporal resolution** — **quarterly**. The cube is published on
  quarter-start months (Jan/Apr/Jul/Oct); we use that native resolution and do
  not resample to a different frequency.
- **Forecast horizon** — **1 period ahead (one quarter)**. Configurable with
  `--horizon`, but the default and validated setting is `h=1`.
- **Features used** — `prodLag1`, `prodLag4`, `prodRollMean4`,
  `employmentGrowth`, `labourCostGrowth`, `quarter`, `month`. All are built with
  `shift(1)` in the feature pipeline, so every predictor for period *t* uses only
  information available at or before *t*. The target is one horizon step in the
  future, so training never sees the value it predicts.

### Models compared

A deliberately small set (not a research ensemble):

1. **naive** — previous-period baseline (predicts the most recent known
   productivity level, the `prodLag1` value). Answers "does any learned model
   beat assuming next quarter looks like this quarter?"
2. **ridge** — regularized linear regression with median imputation and
   standardization, wrapped in a scikit-learn `Pipeline` so preprocessing is fit
   on the training fold only.
3. **random_forest** — tree-based regression with median imputation.

### Train / validation / test separation

Splitting is **chronological**, never shuffled. Cutoffs are computed on the
shared, sorted period axis so every industry series is cut at the same calendar
boundary:

- **train** = earliest periods,
- **validation** = the following block (used for model selection),
- **test** = the newest, fully held-out block (used only to confirm).

Preprocessing (imputation, scaling) lives inside each model's pipeline, so it is
fit on training data only — no leakage from validation/test into training.
The selected model is retrained on train+val before its final test evaluation.

### Selected model and metrics (real backtest, not fabricated)

With the current dataset (train 1997Q2–2014Q2, validation 2014Q3–2020Q1, test
2020Q2–2025Q4), metrics from genuine held-out predictions:

| model         | val MAE | val RMSE | val R² | test MAE | test RMSE | test R² |
|---------------|--------:|---------:|-------:|---------:|----------:|--------:|
| ridge (selected) | 2.816 | 6.711 | 0.693 | 3.332 | 6.207 | 0.392 |
| naive         | 2.840 | 6.763 | 0.688 | 3.096 | 5.265 | 0.563 |
| random_forest | 3.825 | 9.346 | 0.405 | 4.861 | 7.919 | 0.010 |

**ridge** is selected because it has the lowest **validation** MAE. Metrics are
computed from real out-of-sample folds and are reported as-is.

### Important limitations

- **The learned edge is small and does not clearly hold out of sample.** Ridge
  beats the naive baseline on validation only marginally, and on the held-out
  **test** period the naive baseline actually scores better (test MAE 3.10 vs
  3.33). The test window begins in 2020Q2 and includes the COVID-19 shock, where
  a simple previous-value predictor is more robust. This is reported honestly
  rather than tuned away; treat the model as a modest, transparent prototype.
- **Association, not causation.** Feature attributions/coefficients describe
  statistical association. The model does **not** establish that any predictor
  causes productivity to rise or fall.
- **National only.** The ingested data has geography = Canada; there is no
  province-level modelling yet.
- **Weather unused.** No weather has been ingested, so weather features are
  excluded. Training will include them automatically once weather data exists.
- **Random forest overfits** this small, largely linear quarterly series and is
  not competitive here.

### Model artifacts

Training writes a reproducible artifact to `ml/artifacts/<model_version>/`
(git-ignored):

- `model.joblib` — the fitted estimator,
- `metadata.json` — full reproducibility metadata: model type, version, target,
  resolution, horizon, ordered feature names, preprocessing config, train /
  validation / test periods, training timestamp, real metrics for every model,
  the source `FeatureSet` id, and the random seed.

A `latest.txt` pointer records the most recent version so serving code can load
it without scanning.

### Train and predict

```bash
# 1) Build the feature matrix (reads ingested data from PostgreSQL).
cpi-ml generate-features

# 2) Train, evaluate, select, and persist the best model.
cpi-ml train-model                     # defaults: latest FeatureSet, horizon=1
cpi-ml train-model --horizon 1 --val-fraction 0.2 --test-fraction 0.2

# 3) Generate a forecast from the latest artifact (feature values as JSON).
cpi-ml predict --features "{\"prodLag1\": 105.2, \"prodLag4\": 103.1, \"prodRollMean4\": 104.0, \"employmentGrowth\": 0.004, \"labourCostGrowth\": 0.011, \"quarter\": 2, \"month\": 4}" --forecast-period 2026-Q2
# or, from a file:
cpi-ml predict --features-file features.json --model-version <version>
```

Programmatic prediction (independent of the CLI, for the backend to call):

```python
from cpi_ml.prediction import ProductivityForecaster

forecaster = ProductivityForecaster.load("artifacts")   # or a specific version
result = forecaster.predict({"prodLag1": 105.2, "prodLag4": 103.1, ...})
result.prediction        # forecast value
result.model_version     # which model produced it
result.features_used     # exact ordered feature values fed to the model
result.model_metadata    # full reproducibility metadata
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
- Train/validation/test are split chronologically; time-series rows are never
  shuffled and no future information is used to predict the past.
- Model metrics are reported honestly, including when a learned model fails to
  beat the naive baseline.
- SHAP attributions and model coefficients describe association, not causation.
