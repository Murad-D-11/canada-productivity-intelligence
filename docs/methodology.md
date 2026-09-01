# Methodology

This document states, in plain terms, how Canada Productivity Intelligence
handles data and modeling. It is the reference for the in-app Methodology page.

## Data provenance

- Every observation records its source (`STATCAN_WDS`, `MSC_GEOMET`,
  `CANADIAN_SURVEY_BUSINESS_CONDITIONS`), the source identifier (vector/table),
  and the retrieval timestamp.
- Raw payloads are stored under `data/raw/` with a sidecar metadata file
  capturing the request URL, parameters, and time.

## Missing data

- If a source does not publish a value, the value is stored as `null` with the
  original status flag preserved.
- Target values are never silently interpolated. Any imputation used for
  modeling features is explicit, flagged in the data, and documented here.

## Feature construction

- Lag and rolling features use only periods strictly earlier than the row's
  period (`shift`/trailing windows). This prevents look-ahead leakage.

## Forecast evaluation

- Models are validated with an expanding-window backtest: each fold trains on
  all data up to a cut point and evaluates on the immediately following block.
- Reported metrics (MAE, RMSE) come from these genuine out-of-sample folds.
  Metrics are never hard-coded or estimated by hand.
- Each trained model records its `trainingCutoff` so no evaluation can use
  future information.

## Explainability

- Feature importance is computed with SHAP.
- SHAP values describe the statistical **association** between a feature and the
  model's prediction. They are **not** causal effects. The platform does not
  claim that changing a driver will cause a productivity change.

## Scenario simulation

- A scenario applies user-specified adjustments to input features and reports
  the model's simulated output relative to a baseline.
- Because the underlying model is associational, scenario outputs are framed as
  "model-implied" changes, not guaranteed real-world outcomes.

## Data sources

| Source | Use | Documentation |
| --- | --- | --- |
| Statistics Canada Web Data Service | Labour & multifactor productivity, business conditions | https://www.statcan.gc.ca/en/developers/wds/user-guide |
| MSC GeoMet OGC API | Climate/weather covariates | https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/ |
| Canadian Survey on Business Conditions | Business sentiment covariates | https://www.statcan.gc.ca/en/survey/business/5426 |
